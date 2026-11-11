# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
import time
from unittest import TestCase
from unittest.mock import Mock, call, patch

import requests
from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    empty,
    equal_to,
    less_than,
    raises,
)

from ..retry_thread import RetryThread

MODULE = 'wazo_calld.plugin_helpers.retry_thread'
LOGGER = MODULE


class RecordingEvent:
    """A stop event whose waits return at once and are recorded."""

    def __init__(self):
        self.waits = []
        self._set = False

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return self._set

    def set(self):
        self._set = True

    def is_set(self):
        return self._set


class Outcomes:
    """A task answering each call with the next outcome: an exception is raised."""

    def __init__(self, *outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def __call__(self):
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException) or (
            isinstance(outcome, type) and issubclass(outcome, BaseException)
        ):
            raise outcome
        return outcome


class RecordedStopEventTestCase(TestCase):
    def setUp(self):
        self.stop_event = RecordingEvent()
        patcher = patch(f'{MODULE}.Event', return_value=self.stop_event)
        patcher.start()
        self.addCleanup(patcher.stop)


def thread_of(retry_thread):
    thread = retry_thread._thread
    assert thread is not None, 'the retry thread was never started'
    return thread


def run_to_end(retry_thread):
    retry_thread.start()
    thread_of(retry_thread).join(timeout=5)
    if thread_of(retry_thread).is_alive():
        retry_thread.stop()
        raise AssertionError('the retry thread did not end')


class TestRetryThreadDelays(RecordedStopEventTestCase):
    def test_repeated_errors_follow_delays_and_repeat_the_last(self):
        task = Outcomes(*[Exception('down')] * 6, True)
        retry_thread = RetryThread('svc', task, delays=[2, 4, 8, 16, 32])

        run_to_end(retry_thread)

        assert_that(self.stop_event.waits, equal_to([2, 4, 8, 16, 32, 32]))
        assert_that(task.calls, equal_to(7))

    def test_read_timeouts_follow_timeout_delays(self):
        task = Outcomes(*[requests.ReadTimeout('slow')] * 4, True)
        retry_thread = RetryThread(
            'svc',
            task,
            delays=[1],
            timeout_delays=[30, 60, 120],
        )

        run_to_end(retry_thread)

        assert_that(self.stop_event.waits, equal_to([30, 60, 120, 120]))

    def test_read_timeouts_follow_delays_without_timeout_delays(self):
        task = Outcomes(*[requests.ReadTimeout('slow')] * 4, True)
        retry_thread = RetryThread('svc', task, delays=[1])

        run_to_end(retry_thread)

        assert_that(self.stop_event.waits, equal_to([1, 1, 1, 1]))

    def test_each_schedule_keeps_its_own_counter(self):
        task = Outcomes(
            Exception('down'),
            Exception('down'),
            requests.ReadTimeout('slow'),
            Exception('down'),
            True,
        )
        retry_thread = RetryThread(
            'svc',
            task,
            delays=[1, 2, 3],
            timeout_delays=[30, 60],
        )

        run_to_end(retry_thread)

        assert_that(self.stop_event.waits, equal_to([1, 2, 30, 3]))

    def test_a_falsy_return_is_retried_with_the_next_delay(self):
        task = Outcomes(False, None, Exception('down'), True)
        retry_thread = RetryThread('svc', task, delays=[5, 6, 7])

        run_to_end(retry_thread)

        assert_that(self.stop_event.waits, equal_to([5, 6, 7]))
        assert_that(task.calls, equal_to(4))


class TestRetryThreadSuccess(RecordedStopEventTestCase):
    def test_success_calls_each_subscriber_once_in_order_and_never_the_task_again(
        self,
    ):
        task = Outcomes(Exception('down'), 'ready')
        order = Mock()
        retry_thread = RetryThread('svc', task, delays=[1])
        retry_thread.subscribe(order.first)
        retry_thread.subscribe(order.second)

        run_to_end(retry_thread)

        assert_that(task.calls, equal_to(2))
        assert_that(order.mock_calls, contains_exactly(call.first(), call.second()))

    def test_a_subscriber_that_raises_is_logged_and_the_next_one_is_called(self):
        task = Outcomes(True)
        second = Mock()
        retry_thread = RetryThread('svc', task, delays=[1])
        retry_thread.subscribe(Mock(side_effect=RuntimeError('boom')))
        retry_thread.subscribe(second)

        with self.assertLogs(LOGGER, level='ERROR') as logs:
            run_to_end(retry_thread)

        second.assert_called_once_with()
        assert_that(len(logs.records), equal_to(1))
        exc_info = logs.records[0].exc_info
        assert exc_info is not None
        assert_that(exc_info[0], equal_to(RuntimeError))


class TestRetryThreadLogs(RecordedStopEventTestCase):
    def test_each_retry_logs_one_warning_naming_the_delay(self):
        task = Outcomes(False, Exception('down'), True)
        retry_thread = RetryThread('wazo-confd', task, delays=[1, 30])

        with self.assertLogs(LOGGER, level='WARNING') as logs:
            run_to_end(retry_thread)

        assert_that(
            [record.getMessage() for record in logs.records],
            contains_exactly(
                'wazo-confd not ready, retrying in 1 seconds...',
                'wazo-confd not ready, retrying in 30 seconds...',
            ),
        )
        assert_that(
            [record.levelno for record in logs.records],
            contains_exactly(logging.WARNING, logging.WARNING),
        )

    def test_an_exception_also_logs_one_debug_record_with_exc_info(self):
        task = Outcomes(False, ValueError('bad answer'), True)
        retry_thread = RetryThread('svc', task, delays=[1])

        with self.assertLogs(LOGGER, level='DEBUG') as logs:
            run_to_end(retry_thread)

        debug = [r for r in logs.records if r.levelno == logging.DEBUG]
        assert_that(len(debug), equal_to(1))
        exc_info = debug[0].exc_info
        assert exc_info is not None
        assert_that(exc_info[0], equal_to(ValueError))
        assert_that(debug[0].getMessage(), equal_to('svc: ValueError: bad answer'))


class TestRetryThreadStop(TestCase):
    def test_stop_interrupts_a_wait_and_the_task_is_called_exactly_once(self):
        warned = threading.Event()

        class WarnedHandler(logging.Handler):
            def emit(self, record):
                if record.levelno == logging.WARNING:
                    warned.set()

        handler = WarnedHandler()
        logging.getLogger(LOGGER).addHandler(handler)
        self.addCleanup(logging.getLogger(LOGGER).removeHandler, handler)
        task = Mock(side_effect=Exception('down'))
        retry_thread = RetryThread('svc', task, delays=[60])
        retry_thread.start()
        self.addCleanup(retry_thread.stop)
        assert warned.wait(timeout=5), 'no retry was scheduled'
        time.sleep(0.1)  # inside the 60 s wait

        started = time.monotonic()
        retry_thread.stop()
        elapsed = time.monotonic() - started

        assert_that(elapsed, less_than(1))
        assert_that(thread_of(retry_thread).is_alive(), equal_to(False))
        assert_that(task.call_count, equal_to(1))

    def test_a_task_succeeding_after_stop_calls_no_subscriber(self):
        entered, release = threading.Event(), threading.Event()

        def task():
            entered.set()
            release.wait(timeout=5)
            return True

        subscriber = Mock()
        retry_thread = RetryThread('svc', task, delays=[60])
        retry_thread.subscribe(subscriber)
        retry_thread.start()
        self.addCleanup(release.set)
        assert entered.wait(timeout=5)
        stopper = threading.Thread(target=retry_thread.stop)
        stopper.start()
        assert retry_thread._stop_event.wait(timeout=5)

        release.set()
        stopper.join(timeout=5)

        assert_that(stopper.is_alive(), equal_to(False))
        subscriber.assert_not_called()

    def test_a_task_failing_while_stop_is_set_ends_without_a_wait(self):
        stop_event = RecordingEvent()

        def task():
            stop_event.set()
            return False

        subscriber = Mock()
        with patch(f'{MODULE}.Event', return_value=stop_event):
            retry_thread = RetryThread('svc', task, delays=[60])
        retry_thread.subscribe(subscriber)

        run_to_end(retry_thread)

        assert_that(stop_event.waits, empty())
        subscriber.assert_not_called()

    def test_stop_on_a_thread_never_started_returns_at_once(self):
        retry_thread = RetryThread('svc', Mock(), delays=[60])

        started = time.monotonic()
        retry_thread.stop()

        assert_that(time.monotonic() - started, less_than(1))

    def test_stop_twice_is_harmless(self):
        retry_thread = RetryThread('svc', Mock(return_value=True), delays=[60])
        retry_thread.start()

        retry_thread.stop()
        retry_thread.stop()

        assert_that(thread_of(retry_thread).is_alive(), equal_to(False))


class TestRetryThreadContract(TestCase):
    def test_start_twice_raises(self):
        retry_thread = RetryThread('svc', Mock(return_value=True), delays=[1])
        retry_thread.start()
        self.addCleanup(retry_thread.stop)

        assert_that(calling(retry_thread.start), raises(RuntimeError))

    def test_the_thread_is_named_and_not_daemon(self):
        retry_thread = RetryThread('ARI', Mock(return_value=True), delays=[1])
        retry_thread.start()
        retry_thread.stop()

        assert_that(thread_of(retry_thread).name, equal_to('ARI'))
        assert_that(thread_of(retry_thread).daemon, equal_to(False))
