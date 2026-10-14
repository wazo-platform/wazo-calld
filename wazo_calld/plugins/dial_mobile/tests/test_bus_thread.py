# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The push path never waits on confd or ARI from the bus thread.

Every bus handler of wazo-calld runs on one thread, in turn. These tests
drive the dial_mobile handlers with fakes that record which thread called
them, and a fake clock for the PSTN fallback timers.
"""

import heapq
import logging
import threading
import time
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from ari.exceptions import ARINotFound, ARIServerError

from ..bus_consume import EventHandler
from ..notifier import Notifier
from ..services import (
    DialMobileService,
    PSTNFallbackCancelled,
    PSTNFallbackDialAnswered,
    PSTNFallbackDialing,
    PSTNFallbackPending,
    PSTNFallbackTriggering,
    _ContactDialer,
    _event_age,
    _NoSuchChannel,
)

SERVICES = 'wazo_calld.plugins.dial_mobile.services'
ELIGIBLE_USER = {
    'mobile_fallback_enabled': True,
    'mobile_phone_number': '+15550100',
    'lines': [{'id': 42}],
}


def push_event(call_id, user_uuid='user-uuid', timestamp='2026-01-01T00:00:00+00:00'):
    return {
        'UserEvent': 'Pushmobile',
        'WAZO_DST_UUID': user_uuid,
        'WAZO_VIDEO_ENABLED': '0',
        'WAZO_RING_TIME': '30',
        'WAZO_TIMESTAMP': timestamp,
        'CallerIDName': 'Alice',
        'CallerIDNum': '101',
        'Uniqueid': call_id,
        'Linkedid': call_id,
        'ChanVariable': {'WAZO_TENANT_UUID': 'tenant-uuid', 'WAZO_SIP_CALL_ID': 'sip'},
    }


def dial_end_event(call_id, status='CANCEL'):
    return {
        'DestContext': 'wazo_wait_for_registration',
        'DialStatus': status,
        'Linkedid': call_id,
    }


class FakeClock:
    """Drives `threading.Timer` in fake seconds: a timer fires only when
    the test advances the clock past it."""

    def __init__(self):
        self.now = 0.0
        self.timers: list['FakeTimer'] = []

    def timer(self, interval, function, args=()):
        timer = FakeTimer(self, interval, function, args)
        self.timers.append(timer)
        return timer

    def live(self):
        return [t for t in self.timers if t.started and not t.done]

    def advance(self, until):
        while due := sorted(
            (t for t in self.live() if t.fire_at <= until), key=lambda t: t.fire_at
        ):
            self.now = due[0].fire_at
            due[0].fire()
        self.now = until


class FakeTimer:
    def __init__(self, clock, interval, function, args):
        self._clock = clock
        self.interval = interval
        self.function = function
        self.args = args
        self.started = False
        self.done = False
        self.fire_at = None

    def start(self):
        self.started = True
        self.fire_at = self._clock.now + self.interval

    def cancel(self):
        self.done = True

    def fire(self):
        self.done = True
        self.function(*self.args)


class FakeDialer:
    """Stands for `_ContactDialer` where the dialer thread is not the
    subject: it starts nothing."""

    def __init__(self, ari, future_bridge_uuid, channel_id, aor, ringing_time, **kw):
        self.future_bridge_uuid = future_bridge_uuid
        self._caller_channel_id = channel_id
        self.pickup_mark = ''

    def start(self):
        pass

    def stop(self):
        pass

    def kick(self):
        pass

    def _on_channel_gone(self, channel_id):
        if channel_id != self._caller_channel_id:
            raise _NoSuchChannel(channel_id)


class ServiceTestCase(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.ari_client = self.ari.client
        self.confd_client = Mock()
        self.auth_client = Mock()
        self.amid_client = Mock()
        # an answering channel that is not the user's mobile, so
        # join_bridge's push resolution has a channel to read
        self.ari_client.channels.get.return_value = Mock(
            json={'name': 'PJSIP/other-00000001', 'channelvars': {}}
        )
        self.ari_client.channels.getChannelVar.return_value = {'value': ''}
        self.notifier = Mock(Notifier)
        self.clock = FakeClock()
        timer_patch = patch(f'{SERVICES}.threading.Timer', side_effect=self.clock.timer)
        timer_patch.start()
        self.addCleanup(timer_patch.stop)
        self.service = self._make_service()
        self.handler = EventHandler(self.service)

    def tearDown(self):
        self.service.on_calld_stopping()

    def _make_service(self, **kwargs):
        return DialMobileService(
            self.ari,
            self.notifier,
            self.amid_client,
            self.auth_client,
            self.confd_client,
            **kwargs,
        )

    def _timer(self, call_id):
        state = self.service._pstn_fallbacks.get(call_id)
        assert isinstance(state, PSTNFallbackPending), state
        return state.timer


class TestPushFirst(ServiceTestCase):
    # criterion 1
    def test_push_sent_without_confd_call_when_confd_raises(self):
        self.confd_client.users.get.side_effect = requests.HTTPError()

        self.handler._on_user_event(push_event('call-1'))

        self.notifier.push_notification.assert_called_once()
        assert self.confd_client.mock_calls == []

    def test_push_sent_at_once_when_confd_blocks(self):
        def blocking_get(*args, **kwargs):
            time.sleep(2)
            return ELIGIBLE_USER

        self.confd_client.users.get.side_effect = blocking_get

        started = time.monotonic()
        self.handler._on_user_event(push_event('call-1'))
        elapsed = time.monotonic() - started

        self.notifier.push_notification.assert_called_once()
        assert elapsed < 1, elapsed
        assert self.confd_client.mock_calls == []

    # criterion 2
    def test_push_sent_and_timer_armed_for_an_eligible_user(self):
        self.confd_client.users.get.return_value = ELIGIBLE_USER

        self.handler._on_user_event(push_event('call-1'))

        self.notifier.push_notification.assert_called_once()
        assert self._timer('call-1').started

    def test_push_sent_and_timer_armed_for_a_non_eligible_user(self):
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }

        self.handler._on_user_event(push_event('call-1'))

        self.notifier.push_notification.assert_called_once()
        assert self._timer('call-1').started

    def test_a_second_push_for_the_call_replaces_its_timer(self):
        # Push state is keyed by the call's Linkedid: a second push for the
        # same call replaces the first, and so does its timer, which is
        # cancelled instead of left to fire for a state it no longer owns.
        self.handler._on_user_event(push_event('call-1', user_uuid='u1'))
        first = self._timer('call-1')

        self.handler._on_user_event(push_event('call-1', user_uuid='u2'))

        assert first.done
        assert self.clock.live() == [self._timer('call-1')]

    def test_a_second_push_keeps_a_fallback_past_pending(self):
        # A fallback that fired is the call's: a second push for the same
        # call must neither drop it (a live PSTN leg would be untracked) nor
        # arm a second one.
        for state in (
            PSTNFallbackTriggering(call_id='call-1'),
            PSTNFallbackDialing(call_id='call-1', channel_id='pstn-1'),
            PSTNFallbackDialAnswered(call_id='call-1', channel_id='pstn-1'),
        ):
            with self.subTest(state=type(state).__name__):
                self.service._call_locks.setdefault('call-1', threading.RLock())
                self.service._pstn_fallbacks['call-1'] = state
                live_before = len(self.clock.live())

                self.handler._on_user_event(push_event('call-1', user_uuid='u2'))

                assert self.service._pstn_fallbacks['call-1'] is state
                assert len(self.clock.live()) == live_before
                self.notifier.push_notification.assert_called()

    def test_a_second_push_after_a_cancelled_fallback_arms_a_timer(self):
        self.service._call_locks['call-1'] = threading.RLock()
        self.service._pstn_fallbacks['call-1'] = PSTNFallbackCancelled('call-1')

        self.handler._on_user_event(push_event('call-1', user_uuid='u2'))

        assert self._timer('call-1').started


class TestTimerDecides(ServiceTestCase):
    def _ringing_call(self, call_id='call-1'):
        self.handler._on_user_event(push_event(call_id))
        with patch(f'{SERVICES}._ContactDialer', FakeDialer):
            self.service.dial_all_contacts(f'caller-{call_id}', call_id, 'aor')
        self.ari_client.reset_mock()

    # criterion 3
    def test_fallback_disabled_dials_nothing(self):
        self.confd_client.users.get.return_value = dict(
            ELIGIBLE_USER, mobile_fallback_enabled=False
        )
        # with the check removed the run must reach originate
        self.confd_client.lines.get.return_value = {'context': 'outbound'}
        self._ringing_call()

        self._timer('call-1').fire()

        self.confd_client.users.get.assert_called_once()
        self.ari_client.channels.originate.assert_not_called()

    def test_no_mobile_number_dials_nothing(self):
        self.confd_client.users.get.return_value = dict(
            ELIGIBLE_USER, mobile_phone_number=''
        )
        self.confd_client.lines.get.return_value = {'context': 'outbound'}
        self._ringing_call()

        self._timer('call-1').fire()

        self.confd_client.users.get.assert_called_once()
        self.ari_client.channels.originate.assert_not_called()

    # criterion 4
    def test_eligible_user_is_dialed_when_the_timer_fires(self):
        self.confd_client.users.get.return_value = ELIGIBLE_USER
        self.confd_client.lines.get.return_value = {'context': 'outbound'}
        self._ringing_call()
        bridge_uuid = self.service._bridge_uuid_by_origin_call_id['call-1']

        self._timer('call-1').fire()

        self.ari_client.channels.originate.assert_called_once_with(
            endpoint='Local/+15550100@outbound',
            app='dial_mobile',
            appArgs=['join', bridge_uuid],
            callerId='"Alice" <101>',
            originator='caller-call-1',
            variables={'variables': {'_WAZO_TENANT_UUID': 'tenant-uuid'}},
        )

    def test_confd_failure_at_fire_time_aborts(self):
        self.confd_client.users.get.side_effect = requests.RequestException()
        self._ringing_call()

        self._timer('call-1').fire()

        self.ari_client.channels.originate.assert_not_called()
        assert isinstance(self.service._pstn_fallbacks['call-1'], PSTNFallbackCancelled)

    # criterion 7
    def test_answered_call_cancels_its_timer(self):
        self.confd_client.users.get.return_value = ELIGIBLE_USER
        self._ringing_call()
        timer = self._timer('call-1')
        bridge_uuid = self.service._bridge_uuid_by_origin_call_id['call-1']

        self.service.join_bridge('mobile-ch', bridge_uuid)

        assert timer.done
        self.clock.advance(600)
        self.confd_client.users.get.assert_not_called()
        self.ari_client.channels.originate.assert_not_called()

    def test_cancelled_push_cancels_its_timer(self):
        self.confd_client.users.get.return_value = ELIGIBLE_USER
        self._ringing_call()
        timer = self._timer('call-1')

        self.handler._on_dial_end(dial_end_event('call-1'))

        assert timer.done
        self.clock.advance(600)
        self.confd_client.users.get.assert_not_called()
        self.ari_client.channels.originate.assert_not_called()

    def test_unanswered_dial_end_hangs_up_a_dialing_pstn_leg(self):
        # The one ARI call DialEnd keeps on the bus thread: a PSTN leg
        # already originated for a call whose mobile dial ended unanswered.
        self.confd_client.users.get.return_value = ELIGIBLE_USER
        self.confd_client.lines.get.return_value = {'context': 'outbound'}
        self.ari_client.channels.originate.return_value = Mock(id='pstn-1')
        self._ringing_call()
        self._timer('call-1').fire()
        assert isinstance(self.service._pstn_fallbacks['call-1'], PSTNFallbackDialing)

        self.handler._on_dial_end(dial_end_event('call-1', status='NOANSWER'))

        self.ari_client.channels.hangup.assert_called_once_with(channelId='pstn-1')
        assert isinstance(
            self.service._pstn_fallbacks['call-1'], PSTNFallbackCancelled
        )

    def test_answered_dial_end_leaves_the_timer_to_join_bridge(self):
        self._ringing_call()
        timer = self._timer('call-1')

        self.handler._on_dial_end(dial_end_event('call-1', status='ANSWER'))

        assert not timer.done


class TestDialerOwnsItsAriCalls(TestCase):
    def setUp(self):
        self.calls: list[tuple[str, str]] = []
        self.ari = Mock()
        self.ari_client = self.ari.client

        def record(name, value=None):
            def side_effect(*args, **kwargs):
                self.calls.append((name, threading.current_thread().name))
                if isinstance(value, Exception):
                    raise value
                return value

            return side_effect

        self.record = record
        self.ari_client.channels.ring.side_effect = record('ring')
        self.ari_client.channels.getChannelVar.side_effect = record(
            'getChannelVar', {'value': '1001%default'}
        )
        self.ari_client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Alice', 'number': '101'}}
        )
        self.service = DialMobileService(
            self.ari, Mock(Notifier), Mock(), Mock(), Mock()
        )

    def tearDown(self):
        self.service.on_calld_stopping()

    def _dialer(self):
        return _ContactDialer(self.ari_client, 'bridge-uuid', 'caller-ch', 'aor', 30)

    def test_a_dialer_stopped_before_its_run_does_not_ring(self):
        dialer = self._dialer()
        dialer.should_stop.set()

        dialer._run_no_exception('caller-ch', 'aor')

        assert self.ari_client.mock_calls == []

    def test_caller_gone_before_the_ring_ends_the_run_quietly(self):
        self.ari_client.channels.ring.side_effect = ARINotFound(Mock(), Mock())
        dialer = self._dialer()

        with self.assertLogs(SERVICES, logging.DEBUG) as logs:
            dialer._run_no_exception('caller-ch', 'aor')

        assert [r.levelno for r in logs.records if r.levelno >= logging.WARNING] == []
        self.ari_client.channels.getChannelVar.assert_not_called()
        self.ari_client.channels.originate.assert_not_called()

    def test_a_ring_server_error_is_logged_and_ends_the_run(self):
        self.ari_client.channels.ring.side_effect = ARIServerError(Mock(), Mock())
        dialer = self._dialer()

        with self.assertLogs(SERVICES, logging.ERROR):
            dialer._run_no_exception('caller-ch', 'aor')

        self.ari_client.channels.originate.assert_not_called()

    # criterion 5
    def test_dial_all_contacts_makes_no_ari_call(self):
        with patch.object(_ContactDialer, 'start'):
            self.service.dial_all_contacts('caller-ch', 'call-1', 'aor')

        assert self.ari_client.mock_calls == []

    def test_ring_and_pickup_mark_run_on_the_dialer_thread(self):
        self.service.dial_all_contacts('caller-ch', 'call-1', 'aor')
        (dialer,) = self.service._contact_dialers.values()
        dialer.stop()

        assert self.calls[:2] == [
            ('ring', 'ContactDialer'),
            ('getChannelVar', 'ContactDialer'),
        ]
        self.ari_client.channels.ring.assert_called_once_with(channelId='caller-ch')
        self.ari_client.channels.getChannelVar.assert_any_call(
            channelId='caller-ch', variable='PJSIP_ENDPOINT(aor,PICKUPMARK)'
        )
        assert dialer.pickup_mark == '1001%default'
        assert self.service.find_bridge_by_exten_context('1001', 'default') == (
            dialer.future_bridge_uuid
        )

    def test_pickup_mark_lookup_server_error_gives_an_empty_mark(self):
        def get_var(channelId, variable):
            if variable.startswith('PJSIP_ENDPOINT'):
                raise ARIServerError(Mock(), Mock())
            return {'value': ''}

        self.ari_client.channels.getChannelVar.side_effect = get_var

        self.service.dial_all_contacts('caller-ch', 'call-1', 'aor')
        (dialer,) = self.service._contact_dialers.values()
        dialer.stop()

        assert dialer.pickup_mark == ''
        # the run went on to its contacts lookup after the failed mark
        self.ari_client.channels.getChannelVar.assert_any_call(
            channelId='caller-ch', variable='PJSIP_DIAL_CONTACTS(aor)'
        )


class TestMobileTokenWorker(TestCase):
    def setUp(self):
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.http_threads: list[str] = []

        def record(*args, **kwargs):
            self.http_threads.append(threading.current_thread().name)
            return {'filtered': 0}

        self.amid_client.action.side_effect = record
        self.auth_client.token.list.side_effect = record
        self.service = DialMobileService(
            Mock(), Mock(Notifier), self.amid_client, self.auth_client, Mock()
        )
        self.handler = EventHandler(self.service)

    def tearDown(self):
        self.service.on_calld_stopping()

    def _drain(self):
        self.service._token_worker.submit(lambda: None).result(timeout=5)

    def _hints(self):
        return [c.args[1]['Value'] for c in self.amid_client.action.call_args_list]

    # criterion 8
    def test_created_event_returns_without_http_and_worker_sets_hint(self):
        gate = threading.Event()
        self.service._token_worker.submit(gate.wait, 5)

        self.handler._on_refresh_token_created({'mobile': True, 'user_uuid': 'u1'})

        assert self.amid_client.mock_calls == []
        gate.set()
        self._drain()
        assert self._hints() == ['NOT_INUSE']
        assert threading.current_thread().name not in self.http_threads

    def test_deleted_event_returns_without_http_and_worker_sets_hint(self):
        gate = threading.Event()
        self.service._token_worker.submit(gate.wait, 5)

        self.handler._on_refresh_token_deleted({'mobile': True, 'user_uuid': 'u1'})

        assert self.auth_client.mock_calls == []
        assert self.amid_client.mock_calls == []
        gate.set()
        self._drain()
        self.auth_client.token.list.assert_called_once_with('u1', mobile=True)
        assert self._hints() == ['UNAVAILABLE']
        assert threading.current_thread().name not in self.http_threads

    def _held(self):
        gate = threading.Event()
        self.service._token_worker.submit(gate.wait, 5)
        return gate

    def test_last_event_of_a_user_wins(self):
        gate = self._held()
        self.service.on_mobile_refresh_token_deleted('u1')
        self.service.on_mobile_refresh_token_created('u1')
        gate.set()
        self._drain()
        assert self._hints() == ['NOT_INUSE']
        self.auth_client.token.list.assert_not_called()

        self.amid_client.reset_mock()
        gate = self._held()
        self.service.on_mobile_refresh_token_created('u1')
        self.service.on_mobile_refresh_token_deleted('u1')
        gate.set()
        self._drain()
        assert self._hints() == ['UNAVAILABLE']
        self.auth_client.token.list.assert_called_once_with('u1', mobile=True)

    def test_queued_events_cost_one_update_per_user(self):
        gate = self._held()
        for _ in range(50):
            self.service.on_mobile_refresh_token_deleted('u1')
            self.service.on_mobile_refresh_token_created('u1')
        self.service.on_mobile_refresh_token_created('u2')
        gate.set()
        self._drain()

        assert [c.args[1]['Variable'] for c in self.amid_client.action.call_args_list] == [
            'DEVICE_STATE(Custom:u1-mobile)',
            'DEVICE_STATE(Custom:u2-mobile)',
        ]
        self.auth_client.token.list.assert_not_called()

    def test_an_event_during_its_users_update_runs_after_it(self):
        in_update = threading.Event()
        release = threading.Event()

        def slow_setvar(*args, **kwargs):
            in_update.set()
            release.wait(5)

        self.amid_client.action.side_effect = slow_setvar
        self.service.on_mobile_refresh_token_created('u1')
        assert in_update.wait(5)

        self.service.on_mobile_refresh_token_deleted('u1')
        release.set()
        self._drain()

        assert self._hints() == ['NOT_INUSE', 'UNAVAILABLE']

    def test_the_next_job_runs_after_an_auth_failure(self):
        self.auth_client.token.list.side_effect = requests.HTTPError()

        self.service.on_mobile_refresh_token_deleted('u1')
        self.service.on_mobile_refresh_token_created('u2')
        self._drain()

        assert self._hints() == ['NOT_INUSE']

    def test_an_unexpected_error_is_logged_and_the_worker_goes_on(self):
        self.amid_client.action.side_effect = [RuntimeError('amid down'), None]

        with self.assertLogs(SERVICES, logging.ERROR) as logs:
            self.service.on_mobile_refresh_token_created('u1')
            self.service.on_mobile_refresh_token_created('u2')
            self._drain()

        assert self.amid_client.action.call_count == 2
        assert 'amid down' in logs.output[0]

    def test_events_after_stopping_are_dropped_quietly(self):
        self.service.on_calld_stopping()

        self.handler._on_refresh_token_created({'mobile': True, 'user_uuid': 'u1'})
        self.handler._on_refresh_token_deleted({'mobile': True, 'user_uuid': 'u1'})

        with self.assertRaises(RuntimeError):
            self.service._token_worker.submit(lambda: None)
        assert self.amid_client.mock_calls == []
        assert self.auth_client.mock_calls == []


class TestPushLogLine(ServiceTestCase):
    # criterion 9
    def test_push_line_keeps_its_prefix_and_ends_with_the_event_age(self):
        sent_at = datetime(2026, 1, 1, 0, 0, 0, 400000, tzinfo=timezone.utc)

        with patch(f'{SERVICES}._utcnow', return_value=sent_at):
            with self.assertLogs(SERVICES, logging.INFO) as logs:
                self.handler._on_user_event(
                    push_event('call-1', timestamp='2026-01-01T00:00:00.000+00:00')
                )

        (line,) = (m for m in logs.records if 'push notification' in m.getMessage())
        assert line.levelno == logging.INFO
        assert line.getMessage() == (
            'call call-1: Sending incoming call push notification event_age=0.4s'
        )


class TestEventAge(TestCase):
    now = datetime(2026, 1, 1, 0, 1, 0, tzinfo=timezone.utc)

    def test_age_in_seconds(self):
        assert _event_age('2026-01-01T00:00:45.500+00:00', self.now) == '14.5s'

    def test_the_emitters_shape(self):
        # wazo-agid's wake_mobile: datetime.now(tz=timezone.utc).isoformat()
        assert _event_age('2026-01-01T00:00:45.500000+00:00', self.now) == '14.5s'

    def test_other_offset(self):
        assert _event_age('2026-01-01T01:00:59+01:00', self.now) == '1.0s'

    def test_clock_skew_shows_a_negative_age(self):
        assert _event_age('2026-01-01T00:01:02+00:00', self.now) == '-2.0s'

    def test_unparseable_timestamp(self):
        assert _event_age('not a date', self.now) == 'unknown'

    def test_missing_timestamp(self):
        assert _event_age(None, self.now) == 'unknown'

    def test_timestamp_without_offset(self):
        assert _event_age('2026-01-01T00:00:00', self.now) == 'unknown'

    def test_far_timestamp_does_not_overflow(self):
        assert _event_age('1970-01-01T00:00:00+00:00', self.now) == '1767225660.0s'


class TestPeakLoad(ServiceTestCase):
    """Criterion 6: a large mobile-only stack's peak, in fake time."""

    PUSHES = 1300
    WINDOW = 600.0
    FALLBACK_TIMEOUT = 30.0

    def setUp(self):
        super().setUp()
        self.service = self._make_service(
            pstn_fallback_min_timeout=self.FALLBACK_TIMEOUT,
            pstn_fallback_ring_timeout_factor=0.5,
        )
        self.handler = EventHandler(self.service)
        self.confd_client.users.get.return_value = ELIGIBLE_USER
        self.confd_client.lines.get.return_value = {'context': 'outbound'}

    def _bus(self, handler, *args):
        """A push-path bus handler: it must touch neither confd nor ARI."""
        confd_before = len(self.confd_client.mock_calls)
        ari_before = len(self.ari_client.mock_calls)
        handler(*args)
        assert len(self.confd_client.mock_calls) == confd_before, handler
        assert len(self.ari_client.mock_calls) == ari_before, handler

    def test_peak(self):
        events: list[tuple[float, int, str, str]] = []
        seq = 0

        def at(t, kind, call_id):
            nonlocal seq
            seq += 1
            heapq.heappush(events, (t, seq, kind, call_id))

        expected_fallbacks = 0
        for i in range(self.PUSHES):
            t = i * self.WINDOW / self.PUSHES
            call_id = f'call-{i}'
            at(t, 'push', call_id)
            at(t + 0.1, 'dial', call_id)
            match i % 10:
                case 0 | 1 | 2 | 3:
                    at(t + 10, 'answer', call_id)
                case 4 | 5 | 6:
                    at(t + 10, 'cancel', call_id)
                case _:
                    expected_fallbacks += 1
                    at(t + self.FALLBACK_TIMEOUT + 10, 'end', call_id)

        ringing: set[str] = set()
        with patch(f'{SERVICES}._ContactDialer', FakeDialer):
            while events:
                t, _, kind, call_id = heapq.heappop(events)
                self.clock.advance(t)
                match kind:
                    case 'push':
                        ringing.add(call_id)
                        self._bus(self.handler._on_user_event, push_event(call_id))
                    case 'dial':
                        self._bus(
                            self.service.dial_all_contacts,
                            f'caller-{call_id}',
                            call_id,
                            'aor',
                        )
                    case 'answer':
                        bridge = self.service._bridge_uuid_by_origin_call_id[call_id]
                        self.service.join_bridge(f'mobile-{call_id}', bridge)
                        ringing.discard(call_id)
                    case 'cancel':
                        self._bus(self.handler._on_dial_end, dial_end_event(call_id))
                        self.service.notify_channel_gone(f'caller-{call_id}')
                        ringing.discard(call_id)
                    case 'end':
                        self.service.notify_channel_gone(f'caller-{call_id}')
                        ringing.discard(call_id)

                live = len(self.clock.live())
                assert live <= len(ringing), (t, live, len(ringing))
                assert len(self.service._pstn_fallbacks) <= len(ringing)

        confd_reads = self.confd_client.users.get.call_count
        assert confd_reads == expected_fallbacks == 390
        assert confd_reads < self.PUSHES
        assert self.ari_client.channels.originate.call_count == expected_fallbacks
        assert self.service._pstn_fallbacks == {}
        assert self.service._incoming_calls == {}
        assert self.service._call_locks == {}
