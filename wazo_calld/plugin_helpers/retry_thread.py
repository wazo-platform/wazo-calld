# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from itertools import chain, repeat
from threading import Event, Thread
from typing import Any

import requests
from tenacity import RetryCallState, Retrying, retry_if_exception_type, retry_if_result

logger = logging.getLogger(__name__)

# tenacity calls the task once more after an interrupted sleep, before it reads
# `stop`: this is returned instead.
_STOPPED = object()


def _exception(retry_state: RetryCallState) -> BaseException | None:
    outcome = retry_state.outcome
    return outcome.exception() if outcome is not None and outcome.failed else None


def _schedule_wait(
    delays: Sequence[float], timeout_delays: Sequence[float]
) -> Callable[[RetryCallState], float]:
    schedule = chain(delays, repeat(delays[-1]))
    timeout_schedule = chain(timeout_delays, repeat(timeout_delays[-1]))

    def wait(retry_state: RetryCallState) -> float:
        if isinstance(_exception(retry_state), requests.ReadTimeout):
            return next(timeout_schedule)
        return next(schedule)

    return wait


class RetryThread:
    """Runs `task` in a thread named `name` until it returns a truthy value,
    then calls each subscriber, unless `stop()` came first.

    A falsy return or an exception is retried after the next delay of `delays`
    (`timeout_delays` after a `requests.ReadTimeout`), the last one repeating.
    `stop()` interrupts a wait, not a task call in flight; once the task has
    succeeded, every subscriber is called, even if `stop()` lands meanwhile.
    Subscribe before `start()`: the list is not locked.
    """

    def __init__(
        self,
        name: str,
        task: Callable[[], Any],
        delays: Sequence[float],
        timeout_delays: Sequence[float] | None = None,
    ):
        self.name = name
        self._task = task
        self._wait = _schedule_wait(
            delays, delays if timeout_delays is None else timeout_delays
        )
        self._stop_event = Event()
        self._subscribers: list[Callable[[], Any]] = []
        self._thread: Thread | None = None

    def subscribe(self, callback: Callable[[], Any]) -> None:
        self._subscribers.append(callback)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError(f'{self.name} retry thread already started')
        self._thread = Thread(target=self._run, name=self.name)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            logger.debug('joining %s retry thread...', self.name)
            self._thread.join()

    def _run(self) -> None:
        retrying = Retrying(
            sleep=self._stop_event.wait,
            retry=retry_if_exception_type(Exception)
            | retry_if_result(lambda result: not result),
            wait=self._wait,
            before_sleep=self._log_retry,
            stop=lambda _: self._stop_event.is_set(),
            retry_error_callback=lambda _: _STOPPED,
        )
        retrying(self._attempt)
        if self._stop_event.is_set():
            return
        for subscriber in self._subscribers:
            try:
                subscriber()
            except Exception:
                logger.exception('%s: a subscriber failed', self.name)

    def _attempt(self) -> Any:
        if self._stop_event.is_set():
            return _STOPPED
        return self._task()

    def _log_retry(self, retry_state: RetryCallState) -> None:
        exception = _exception(retry_state)
        if exception is not None:
            logger.debug(
                '%s: %s: %s',
                self.name,
                type(exception).__name__,
                exception,
                exc_info=exception,
            )
        assert retry_state.next_action is not None
        logger.warning(
            '%s not ready, retrying in %g seconds...',
            self.name,
            retry_state.next_action.sleep,
        )
