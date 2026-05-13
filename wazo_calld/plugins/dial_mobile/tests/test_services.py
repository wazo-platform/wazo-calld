# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from unittest import TestCase
from unittest.mock import Mock, patch
from unittest.mock import sentinel as s

import pytest
import requests
from ari.exceptions import ARINotFound
from hamcrest import assert_that, contains_exactly, empty, equal_to, has_items

from ..notifier import Notifier
from ..services import (
    DialMobileService,
    IncomingCallNotified,
    IncomingCallPending,
    IncomingCallPushCancelled,
    IncomingCallReceived,
    PSTNFallbackCancelled,
    PSTNFallbackDialing,
    PSTNFallbackPending,
    _ContactDialer,
    _NoSuchChannel,
)


class DialerTestCase(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.future_bridge_uuid = '6e2b692a-ff56-4121-932d-d208dd5c3362'
        self.aor = 'foobar'
        self.channel_id = '1234567890.42'
        self.ringing_time = 42
        self.pickup_mark = '1003%default'

        self.poller = _ContactDialer(
            self.ari,
            self.future_bridge_uuid,
            self.channel_id,
            self.aor,
            self.ringing_time,
            self.pickup_mark,
        )


class TestSendContactToCurrentCall(DialerTestCase):
    def test_sending_the_same_contact_twice(self):
        self.poller._send_contact_to_current_call(
            s.contact, self.future_bridge_uuid, s.caller_id
        )

        self.ari.reset_mock()

        self.poller._send_contact_to_current_call(
            s.contact, self.future_bridge_uuid, s.caller_id
        )

        self.ari.channels.originate.assert_not_called()

    def test_that_dialed_channels_are_tracked(self):
        self.poller._send_contact_to_current_call(
            s.contact, self.future_bridge_uuid, s.caller_id
        )

        assert_that(
            self.poller._dialed_channels,
            has_items(
                self.ari.channels.originate.return_value,
            ),
        )

    def test_that_the_call_is_sent_to_dial_mobile_join(self):
        self.poller._send_contact_to_current_call(
            s.contact, self.future_bridge_uuid, s.caller_id
        )

        self.ari.channels.originate.assert_called_once_with(
            endpoint=s.contact,
            app='dial_mobile',
            appArgs=['join', self.future_bridge_uuid],
            callerId=s.caller_id,
            originator=self.channel_id,
            timeout=self.ringing_time,
        )


class TestChannelIsUp(DialerTestCase):
    def test_no_channel(self):
        self.ari.channels.get.side_effect = ARINotFound(s.ari_client, s.original_error)

        result = self.poller._channel_is_up(s.channel_id)

        assert_that(result, equal_to(False))

    def test_with_channel(self):
        self.ari.channels.get.return_value = s.channel

        result = self.poller._channel_is_up(s.channel_id)

        assert_that(result, equal_to(True))


class TestGetContacts(DialerTestCase):
    def test_no_result(self):
        self.ari.channels.getChannelVar.return_value = {'value': ''}

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, empty())

    def test_no_channel(self):
        self.ari.channels.getChannelVar.side_effect = ARINotFound(
            s.ari_client, s.original_error
        )

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, empty())

    def test_one_value(self):
        self.ari.channels.getChannelVar.return_value = {'value': 'contact1'}

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, contains_exactly('contact1'))

    def test_multiple_values(self):
        self.ari.channels.getChannelVar.return_value = {
            'value': 'contact1&contact2&contact3'
        }

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, contains_exactly('contact1', 'contact2', 'contact3'))


class TestRemoveUnansweredChannels(DialerTestCase):
    def test_that_hungup_channels_do_not_interrupt(self):
        channel_1 = Mock()
        channel_1.get.side_effect = ARINotFound(s.ari_client, s.original_error)

        channel_2 = Mock()
        channel_2.id = s.channel_2_id
        channel_2.get.return_value = Mock(json={'state': 'Ringing'})
        # set is replaced with a list to enforce the looping order
        self.poller._dialed_channels = {channel_1, channel_2}

        self.poller._remove_unanswered_channels()

        self.ari.channels.hangup.assert_called_once_with(channelId=s.channel_2_id)

    def test_that_channels_hanging_up_during_the_execution_do_not_interrupt(self):
        channel_1 = Mock()
        channel_1.id = s.channel_1_id
        channel_1.get.return_value = Mock(json={'state': 'Ringing'})

        channel_2 = Mock()
        channel_2.id = s.channel_2_id
        channel_2.get.return_value = Mock(json={'state': 'Ringing'})
        # set is replaced with a list to enforce the looping order
        self.poller._dialed_channels = [channel_1, channel_2]  # type: ignore[assignment]

        def hangup_mock(channelId):
            if channelId == s.channel_1_id:
                raise ARINotFound(s.ari_client, s.original_error)

        self.ari.channels.hangup.side_effect = hangup_mock

        self.poller._remove_unanswered_channels()

        self.ari.channels.hangup.assert_called_with(channelId=s.channel_2_id)

    def test_that_channels_that_are_not_ringing_yet_are_removed(self):
        channel_1 = Mock()
        channel_1.id = s.channel_1_id
        channel_1.get.return_value = Mock(json={'state': 'Down'})

        self.poller._dialed_channels = {channel_1}

        self.poller._remove_unanswered_channels()

        self.ari.channels.hangup.assert_called_with(channelId=s.channel_1_id)


class TestChannelGone(DialerTestCase):
    def test_unknown_channel_gone(self):
        dialed_channel = Mock()
        dialed_channel.id = s.dialed_channel_id
        self.poller._dialed_channels = {dialed_channel}

        with pytest.raises(_NoSuchChannel):
            self.poller._on_channel_gone('unknown')

    def test_caller_gone_before_dialed_any_channel(self):
        self.poller._dialed_channels = set()
        self.poller.stop = Mock()  # type: ignore

        self.poller._on_channel_gone(self.poller._caller_channel_id)

        self.poller.stop.assert_called_once_with()

    def test_dialed_channel_gone(self):
        dialed_channel = Mock()
        dialed_channel.id = s.dialed_channel_id
        self.poller._dialed_channels = {dialed_channel}
        self.poller.stop = Mock()  # type: ignore

        self.poller._on_channel_gone(s.dialed_channel_id)

        self.poller.stop.assert_called_once_with()
        self.ari.channels.hangup.assert_called_with(
            channelId=self.poller._caller_channel_id, reason_code=21
        )


class DialMobileServiceTestCase(DialerTestCase):
    def setUp(self):
        self.ari = Mock()
        self.ari.client = self.ari_client = Mock()
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.confd_client = Mock()
        self.notifier = Mock(Notifier)
        self.service = DialMobileService(
            self.ari,
            self.notifier,
            self.amid_client,
            self.auth_client,
            self.confd_client,
        )
        self.channel_id = '1234567890.42'
        self.aor = 'foobar'
        self.origin_channel_id = '1234567890.84'

    def test_that_caller_channel_rings(self):
        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}

        self.service.dial_all_contacts(
            self.channel_id, self.origin_channel_id, self.aor
        )

        self.ari.client.channels.ring.assert_called_once_with(channelId=self.channel_id)

    def test_set_user_hint_no_mobile_session(self):
        self.service._set_user_hint('<the-uuid>', False)

        self.amid_client.action.assert_called_once_with(
            'Setvar',
            {
                'Variable': 'DEVICE_STATE(Custom:<the-uuid>-mobile)',
                'Value': 'UNAVAILABLE',
            },
        )

    def test_set_user_hint_with_mobile_session(self):
        self.service._set_user_hint('<the-uuid>', True)

        self.amid_client.action.assert_called_once_with(
            'Setvar',
            {
                'Variable': 'DEVICE_STATE(Custom:<the-uuid>-mobile)',
                'Value': 'NOT_INUSE',
            },
        )

    def test_on_mobile_refresh_token_created(self):
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_created(s.user_uuid)
            mock.assert_called_once_with(s.user_uuid, True)

    def test_on_mobile_refresh_token_deleted(self):
        self.auth_client.token.list.return_value = {
            'items': [],
            'filtered': 0,
            'total': 42,
        }
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_deleted(s.user_uuid)
            mock.assert_called_once_with(s.user_uuid, False)

        self.auth_client.token.list.return_value = {
            'items': [{'uuid': 'some-uuid'}],
            'filtered': 1,
            'total': 42,
        }
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_deleted(s.user_uuid)
            mock.assert_called_once_with(s.user_uuid, True)

        self.auth_client.token.list.side_effect = requests.HTTPError()
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_deleted(s.user_uuid)
            mock.assert_not_called()

    def test_notify_channel_gone_on_rejection_hangs_up_caller(self):
        caller_channel_id = '1234567890.42'
        dialed_channel_id = '1234567890.99'

        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}
        self.ari.client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Test', 'number': '1001'}}
        )

        self.service.dial_all_contacts(
            caller_channel_id, self.origin_channel_id, self.aor
        )

        assert_that(len(self.service._contact_dialers), equal_to(1))
        bridge_uuid = next(iter(self.service._contact_dialers))
        dialer = self.service._contact_dialers[bridge_uuid]
        # Simulate the poller having dialed a channel
        mock_dialed_channel = Mock()
        mock_dialed_channel.id = dialed_channel_id
        dialer._dialed_channels.add(mock_dialed_channel)
        dialer.stop()

        self.service.notify_channel_gone(dialed_channel_id)

        self.ari_client.channels.hangup.assert_called_with(
            channelId=caller_channel_id, reason_code=21
        )
        assert_that(self.service._contact_dialers, equal_to({}))

    def test_notify_channel_gone_cancels_pstn_timer(self):
        caller_channel_id = '1234567890.42'
        dialed_channel_id = '1234567890.99'

        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}
        self.ari.client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Test', 'number': '1001'}}
        )

        self.service.dial_all_contacts(
            caller_channel_id, self.origin_channel_id, self.aor
        )

        bridge_uuid = next(iter(self.service._contact_dialers))
        dialer = self.service._contact_dialers[bridge_uuid]
        mock_dialed_channel = Mock()
        mock_dialed_channel.id = dialed_channel_id
        dialer._dialed_channels.add(mock_dialed_channel)
        dialer.stop()
        # PSTN fallback state is keyed by the call's linkedid
        # (origin_call_id), which here is self.origin_channel_id.
        timer = Mock()
        self.service._pstn_fallbacks[self.origin_channel_id] = PSTNFallbackPending(
            call_id=self.origin_channel_id, timer=timer
        )
        self.service._call_locks[self.origin_channel_id] = threading.RLock()
        # mock cancel_push_mobile so it does NOT cancel the timer — proves
        # notify_channel_gone cancels it independently
        with patch.object(self.service, 'cancel_push_mobile'):
            self.service.notify_channel_gone(dialed_channel_id)

        timer.cancel.assert_called_once()

    def test_join_bridge_unknown_future_bridge_will_hangup(self):
        self.service._origin_call_id_by_bridge_uuid[s.bridge_uuid] = s.call_id

        with patch.object(self.service, 'cancel_push_mobile') as push_cancel:
            self.service.join_bridge(s.channel_id, s.bridge_uuid)
            push_cancel.assert_not_called()

        self.ari_client.channels.hangup.assert_called_once_with(channelId=s.channel_id)

    def test_join_bridge_caller_gone_will_hangup(self):
        dialer = Mock()
        self.service._contact_dialers = {s.bridge_uuid: dialer}
        self.service._caller_channel_leg_by_bridge = {s.bridge_uuid: s.caller_channel}
        self.service._origin_call_id_by_bridge_uuid[s.bridge_uuid] = s.call_id
        self.ari_client.channels.answer.side_effect = ARINotFound(
            self.ari_client, s.error
        )

        with patch.object(self.service, 'cancel_push_mobile') as push_cancel:
            self.service.join_bridge(s.channel_id, s.bridge_uuid)
            push_cancel.assert_called_once_with(s.call_id)

        dialer.stop.assert_called_once_with()

        self.ari_client.channels.hangup.assert_called_once_with(channelId=s.channel_id)


class TestCancelPushNotification(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.notifier = Mock(Notifier)
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.confd_client = Mock()
        self.service = DialMobileService(
            self.ari,
            self.notifier,
            self.amid_client,
            self.auth_client,
            self.confd_client,
        )

    def _make_notified(self):
        return IncomingCallNotified(
            call_id=s.call_id,
            tenant_uuid=s.tenant_uuid,
            user_uuid=s.user_uuid,
            origin_call_id=s.call_id,
            payload={'peer_caller_id_name': 'Alice', 'peer_caller_id_number': '101'},
        )

    def test_that_nothing_happens_when_not_a_pending_push(self):
        self.service.cancel_push_mobile(s.call_id)

    def test_complete_push_mobile_transitions_to_received(self):
        self.service._incoming_calls[s.call_id] = self._make_notified()

        self.service.complete_pending_push_mobile(s.call_id)

        self.notifier.cancel_push_notification.assert_not_called()
        assert isinstance(self.service._incoming_calls[s.call_id], IncomingCallReceived)

    def test_cancel_push_mobile_transitions_notified_to_cancelled(self):
        self.service._incoming_calls[s.call_id] = self._make_notified()

        self.service.cancel_push_mobile(s.call_id)

        assert isinstance(
            self.service._incoming_calls[s.call_id], IncomingCallPushCancelled
        )

    def test_cancel_push_mobile_transitions_pending_directly_to_cancelled(self):
        # The Pending → Cancelled transition must be direct (no push to
        # cancel, since none was sent yet).
        self.service._incoming_calls[s.call_id] = IncomingCallPending(
            call_id=s.call_id,
            tenant_uuid=s.tenant_uuid,
            user_uuid=s.user_uuid,
            origin_call_id=s.call_id,
            payload={},
        )

        self.service.cancel_push_mobile(s.call_id)

        self.notifier.cancel_push_notification.assert_not_called()
        assert isinstance(
            self.service._incoming_calls[s.call_id], IncomingCallPushCancelled
        )

    def test_cancel_push_mobile_terminal_state_is_idempotent(self):
        self.service._incoming_calls[s.call_id] = self._make_notified().push_cancelled()

        self.service.cancel_push_mobile(s.call_id)
        # Already terminal — no second cancellation dispatched.
        self.notifier.cancel_push_notification.assert_not_called()

    @patch('wazo_calld.plugins.dial_mobile.services.threading.Timer')
    def test_that_original_payload_is_sent_when_canceling(self, _mock_timer):
        self.service.send_push_notification(
            s.tenant_uuid,
            s.user_uuid,
            s.call_id,
            s.sip_call_id,
            s.cid_name,
            s.cid_num,
            s.video_enabled,
            30,
            s.call_id,
            s.push_mobile_timestamp,
        )

        payload = self.notifier.push_notification.call_args_list[0][0][0]

        self.service.cancel_push_mobile(s.call_id)

        self.notifier.cancel_push_notification.assert_called_once_with(
            payload, s.tenant_uuid, s.user_uuid
        )


class TestPSTNFallback(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.ari.client = self.ari_client = Mock()
        self.notifier = Mock(Notifier)
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.confd_client = Mock()
        self.service = DialMobileService(
            self.ari,
            self.notifier,
            self.amid_client,
            self.auth_client,
            self.confd_client,
        )

    def _make_notified(self, call_id='call-id', origin_call_id='call-id'):
        return IncomingCallNotified(
            call_id=call_id,
            tenant_uuid='tenant-uuid',
            user_uuid='user-uuid',
            origin_call_id=origin_call_id,
            payload={
                'peer_caller_id_name': 'Alice',
                'peer_caller_id_number': '101',
            },
        )

    def _make_pending(self, call_id='call-id', origin_call_id='call-id'):
        return IncomingCallPending(
            call_id=call_id,
            tenant_uuid='tenant-uuid',
            user_uuid='user-uuid',
            origin_call_id=origin_call_id,
            payload={
                'peer_caller_id_name': 'Alice',
                'peer_caller_id_number': '101',
            },
        )

    def _send_push(self, **overrides):
        kwargs = {
            'tenant_uuid': 't-uuid',
            'user_uuid': 'u-uuid',
            'call_id': 'call-id',
            'sip_call_id': 'sip-id',
            'caller_id_name': 'Alice',
            'caller_id_number': '101',
            'video_enabled': False,
            'ring_timeout': 30,
            'origin_call_id': 'call-id',
            'push_mobile_timestamp': 'ts',
        }
        kwargs.update(overrides)
        self.service.send_push_notification(**kwargs)

    def test_push_state_keyed_by_origin_call_id(self):
        # Internal state must be keyed by the call's linkedid
        # (origin_call_id) so the bus-consumer paths — which only know the
        # linkedid — can look up the state created by send_push_notification.
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }

        self._send_push(call_id='channel-uniqueid', origin_call_id='call-linkedid')

        assert 'call-linkedid' in self.service._incoming_calls
        assert 'channel-uniqueid' not in self.service._incoming_calls
        assert 'call-linkedid' in self.service._call_locks
        assert 'channel-uniqueid' not in self.service._call_locks

    def test_pstn_fallback_state_keyed_by_origin_call_id(self):
        # Same invariant for the PSTN fallback state machine.
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': '+33123456789',
        }

        with patch('wazo_calld.plugins.dial_mobile.services.threading.Timer'):
            self._send_push(call_id='channel-uniqueid', origin_call_id='call-linkedid')

        assert 'call-linkedid' in self.service._pstn_fallbacks
        assert 'channel-uniqueid' not in self.service._pstn_fallbacks

    def test_cancel_push_mobile_called_with_linkedid_finds_state(self):
        # The bus consumer passes the linkedid (origin_call_id) when
        # cancelling. Even when the Pushmobile event's Uniqueid differs
        # from the Linkedid, cancel_push_mobile(linkedid) must dispatch
        # the cancellation.
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }
        self._send_push(call_id='channel-uniqueid', origin_call_id='call-linkedid')

        self.service.cancel_push_mobile('call-linkedid')

        self.notifier.cancel_push_notification.assert_called_once()

    def test_complete_pending_push_mobile_called_with_linkedid_finds_state(self):
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }
        self._send_push(call_id='channel-uniqueid', origin_call_id='call-linkedid')

        self.service.complete_pending_push_mobile('call-linkedid')
        from ..services import IncomingCallReceived

        assert isinstance(
            self.service._incoming_calls['call-linkedid'], IncomingCallReceived
        )

    @patch('wazo_calld.plugins.dial_mobile.services.threading.Timer')
    def test_pstn_fallback_timer_starts_on_push_notification(self, mock_timer_cls):
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': '+33123456789',
        }

        self._send_push()

        mock_timer_cls.assert_called_once_with(
            15.0, self.service._pstn_fallback, args=['call-id']
        )
        mock_timer_cls.return_value.start.assert_called_once()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackPending
        )

    def test_send_push_notification_always_creates_call_lock(self):
        # The per-call lock must be created on every push so concurrent
        # IncomingCall transitions can be serialized, even when no PSTN
        # fallback is armed for the call.
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }

        self._send_push()

        assert 'call-id' in self.service._call_locks

    def test_call_lock_reused_across_transitions(self):
        # Reusing the same RLock across transitions is what gives us
        # mutual exclusion; if a second push call for the same id
        # somehow arrived, it must not replace the lock another thread
        # may currently be holding.
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }
        self._send_push()
        first_lock = self.service._call_locks['call-id']

        self._send_push()
        second_lock = self.service._call_locks['call-id']

        assert first_lock is second_lock

    def test_push_not_sent_when_cancelled_during_eligibility_lookup(self):
        # Race: caller hangs up while send_push_notification has released
        # the per-call lock to query confd for fallback eligibility. The
        # concurrent cancel_push_mobile must take effect — the push must
        # not be dispatched and the Cancelled state must not be overwritten.
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': None,
        }

        real_eligible = self.service._pstn_fallback_eligible

        def cancel_then_eligible(user_uuid, tenant_uuid):
            self.service.cancel_push_mobile('call-id')
            return real_eligible(user_uuid, tenant_uuid)

        with patch.object(
            self.service,
            '_pstn_fallback_eligible',
            side_effect=cancel_then_eligible,
        ):
            self._send_push()

        self.notifier.push_notification.assert_not_called()
        assert isinstance(
            self.service._incoming_calls['call-id'], IncomingCallPushCancelled
        )

    @patch('wazo_calld.plugins.dial_mobile.services.threading.Timer')
    def test_pstn_fallback_timer_skipped_when_disabled(self, mock_timer_cls):
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': '+33123456789',
        }

        self._send_push()

        mock_timer_cls.assert_not_called()
        assert not isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackPending
        )

    @patch('wazo_calld.plugins.dial_mobile.services.threading.Timer')
    def test_pstn_fallback_timer_skipped_when_no_mobile_number(self, mock_timer_cls):
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': None,
        }

        self._send_push()

        mock_timer_cls.assert_not_called()
        assert not isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackPending
        )

    @patch('wazo_calld.plugins.dial_mobile.services.threading.Timer')
    def test_pstn_fallback_timer_armed_on_confd_error(self, mock_timer_cls):
        # If we can't determine eligibility, preserve the existing behavior:
        # arm the timer and let _pstn_fallback handle the re-check.
        self.confd_client.users.get.side_effect = requests.HTTPError()

        self._send_push()

        mock_timer_cls.assert_called_once()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackPending
        )

    def test_cancel_push_does_not_touch_pstn_timer(self):
        timer = Mock()
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=timer
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.service._incoming_calls['call-id'] = self._make_notified()

        self.service.cancel_push_mobile('call-id')

        timer.cancel.assert_not_called()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackPending
        )

    def test_cancel_push_noop_when_pending_not_notified(self):
        self.service._incoming_calls['call-id'] = self._make_pending()

        self.service.cancel_push_mobile('call-id')

        self.notifier.cancel_push_notification.assert_not_called()

    def test_pstn_fallback_timer_cancelled_on_join_bridge(self):
        timer = Mock()
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=timer
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.service._origin_call_id_by_bridge_uuid['bridge-uuid'] = 'call-id'

        dialer = Mock()
        self.service._contact_dialers['bridge-uuid'] = dialer
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'

        self.service.join_bridge('mobile-ch', 'bridge-uuid')

        timer.cancel.assert_called_once()

    def test_pstn_fallback_noop_when_no_pending_push(self):
        self.service._pstn_fallback('nonexistent-call-id')

        self.ari_client.channels.originate.assert_not_called()

    def test_pstn_fallback_noop_when_fallback_disabled(self):
        self.service._incoming_calls['call-id'] = self._make_notified()
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': False,
            'mobile_phone_number': '+33123456789',
            'lines': [{'id': 42}],
        }

        self.service._pstn_fallback('call-id')

        self.ari_client.channels.originate.assert_not_called()

    def test_pstn_fallback_noop_when_no_mobile_number(self):
        self.service._incoming_calls['call-id'] = self._make_notified()
        self.service._bridge_uuid_by_origin_call_id['call-id'] = 'bridge-uuid'
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': None,
            'lines': [],
        }

        self.service._pstn_fallback('call-id')

        self.ari_client.channels.originate.assert_not_called()

    def test_pstn_fallback_originates_local_channel(self):
        self.service._incoming_calls['call-id'] = self._make_notified()
        self.service._bridge_uuid_by_origin_call_id['call-id'] = 'bridge-uuid'
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=Mock()
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': '+33123456789',
            'lines': [{'id': 42}],
        }
        self.confd_client.lines.get.return_value = {'context': 'my-outbound-context'}

        self.service._pstn_fallback('call-id')

        self.ari_client.channels.originate.assert_called_once_with(
            endpoint='Local/+33123456789@my-outbound-context',
            app='dial_mobile',
            appArgs=['join', 'bridge-uuid'],
            callerId='"Alice" <101>',
            originator='caller-ch',
            variables={'variables': {'_WAZO_TENANT_UUID': 'tenant-uuid'}},
        )

    def test_notify_contact_available_kicks_matching_dialers(self):
        dialer_a = Mock()
        dialer_b = Mock()
        dialer_other = Mock()
        self.service._dialers_by_aor = {
            'aor-a': {dialer_a, dialer_b},
            'aor-b': {dialer_other},
        }

        self.service.notify_contact_available('aor-a')

        dialer_a.kick.assert_called_once_with()
        dialer_b.kick.assert_called_once_with()
        dialer_other.kick.assert_not_called()

    def test_notify_contact_available_unknown_aor_is_noop(self):
        self.service.notify_contact_available('unknown-aor')

    def test_dial_all_contacts_registers_dialer_by_aor(self):
        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}
        self.ari.client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Test', 'number': '1001'}}
        )

        self.service.dial_all_contacts('caller-ch', 'call-id', 'my-aor')

        bridge_uuid = next(iter(self.service._contact_dialers))
        dialer = self.service._contact_dialers[bridge_uuid]
        assert dialer in self.service._dialers_by_aor['my-aor']
        # Cleanup
        dialer.stop()

    def test_pstn_fallback_records_originated_channel_id(self):
        self.service._incoming_calls['call-id'] = self._make_notified()
        self.service._bridge_uuid_by_origin_call_id['call-id'] = 'bridge-uuid'
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=Mock()
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': '+33123456789',
            'lines': [{'id': 42}],
        }
        self.confd_client.lines.get.return_value = {'context': 'my-outbound-context'}
        originated_channel = Mock()
        originated_channel.id = 'pstn-channel-id'
        self.ari_client.channels.originate.return_value = originated_channel

        self.service._pstn_fallback('call-id')

        state = self.service._pstn_fallbacks.get('call-id')
        assert isinstance(state, PSTNFallbackDialing)
        assert state.channel_id == 'pstn-channel-id'

    def test_cancel_pstn_fallback_hangs_up_active_pstn_channel(self):
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackDialing(
            call_id='call-id',
            channel_id='pstn-channel-id',
        )
        self.service._call_locks['call-id'] = threading.RLock()

        self.service._cancel_pstn_fallback('call-id')

        self.ari_client.channels.hangup.assert_called_once_with(
            channelId='pstn-channel-id'
        )
        assert not isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackDialing
        )

    def test_cancel_pstn_fallback_swallows_already_gone(self):
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackDialing(
            call_id='call-id',
            channel_id='pstn-channel-id',
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.ari_client.channels.hangup.side_effect = ARINotFound(
            self.ari_client, s.error
        )

        self.service._cancel_pstn_fallback('call-id')

        assert not isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackDialing
        )

    def test_join_bridge_hangs_up_active_pstn_channel(self):
        # pickup or mobile-answer must tear down an in-progress PSTN call
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackDialing(
            call_id='call-id',
            channel_id='pstn-channel-id',
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.service._origin_call_id_by_bridge_uuid['bridge-uuid'] = 'call-id'

        dialer = Mock()
        self.service._contact_dialers['bridge-uuid'] = dialer
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'

        self.service.join_bridge('answering-ch', 'bridge-uuid')

        self.ari_client.channels.hangup.assert_any_call(channelId='pstn-channel-id')

    def test_join_bridge_pstn_channel_itself_joining_is_not_hung_up(self):
        # When the PSTN-fallback call answers, its channel enters dial_mobile
        # with action='join'. We must NOT hang up the channel we're about to
        # bridge to the caller.
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackDialing(
            call_id='call-id',
            channel_id='pstn-channel-id',
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.service._origin_call_id_by_bridge_uuid['bridge-uuid'] = 'call-id'

        dialer = Mock()
        self.service._contact_dialers['bridge-uuid'] = dialer
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'

        self.service.join_bridge('pstn-channel-id', 'bridge-uuid')
        # PSTN channel must not be hung up
        for call in self.ari_client.channels.hangup.call_args_list:
            assert call.kwargs.get('channelId') != 'pstn-channel-id'
        # Tracking should still be cleared
        assert not isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackDialing
        )

    def test_notify_channel_gone_caller_gone_hangs_up_active_pstn_channel(self):
        caller_channel_id = '1234567890.42'
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackDialing(
            call_id='call-id',
            channel_id='pstn-channel-id',
        )
        self.service._call_locks['call-id'] = threading.RLock()

        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}
        self.ari.client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Test', 'number': '1001'}}
        )
        self.service.dial_all_contacts(caller_channel_id, 'call-id', 'aor')
        bridge_uuid = next(iter(self.service._contact_dialers))
        dialer = self.service._contact_dialers[bridge_uuid]
        dialer.stop()

        with patch.object(self.service, 'cancel_push_mobile'):
            self.service.notify_channel_gone(caller_channel_id)

        self.ari_client.channels.hangup.assert_any_call(channelId='pstn-channel-id')

    def test_on_contact_dialed_cancels_pstn_fallback(self):
        # When the mobile registers and we originate the SIP INVITE,
        # the PSTN fallback must be cancelled.
        timer = Mock()
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=timer
        )
        self.service._call_locks['call-id'] = threading.RLock()

        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}
        self.ari.client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Test', 'number': '1001'}}
        )
        self.service.dial_all_contacts('caller-ch', 'call-id', 'aor')

        bridge_uuid = next(iter(self.service._contact_dialers))
        dialer = self.service._contact_dialers[bridge_uuid]
        dialer.stop()
        # Simulate the polling thread finding a contact and dialing it.
        dialer._send_contact_to_current_call('sip:contact', bridge_uuid, 'caller-id')

        timer.cancel.assert_called_once()

    def _setup_eligible_fallback(self):
        # Populate the state needed for _pstn_fallback to reach the commit
        # lock without short-circuiting.
        self.service._incoming_calls['call-id'] = self._make_notified()
        self.service._bridge_uuid_by_origin_call_id['call-id'] = 'bridge-uuid'
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=Mock()
        )
        self.service._call_locks['call-id'] = threading.RLock()
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': '+33123456789',
            'lines': [{'id': 42}],
        }
        self.confd_client.lines.get.return_value = {'context': 'my-outbound-context'}

    def test_pstn_fallback_aborts_when_cancelled(self):
        # _cancel_pstn_fallback was called before _pstn_fallback could reach
        # the commit lock. Inside the lock, _pstn_fallback re-reads the
        # state and aborts when it isn't Pending anymore.
        self._setup_eligible_fallback()
        # Cancelled state replaces the Pending state seeded by _setup.
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackCancelled('call-id')

        with patch.object(self.service, 'cancel_push_mobile') as cancel_push:
            self.service._pstn_fallback('call-id')

        cancel_push.assert_not_called()
        self.ari_client.channels.originate.assert_not_called()

    def test_pstn_fallback_originates_when_not_cancelled(self):
        # Sanity check that the lock-protected commit path still runs when
        # no cancellation is signalled.
        self._setup_eligible_fallback()

        self.service._pstn_fallback('call-id')

        self.ari_client.channels.originate.assert_called_once()

    def test_pstn_fallback_originate_failure_preserves_push(self):
        # If originate fails, the push must remain active so the mobile can
        # still register and answer. Cancelling push before a confirmed PSTN
        # dispatch would silently drop the call when originate raises.
        self._setup_eligible_fallback()
        self.ari_client.channels.originate.side_effect = requests.HTTPError()

        with patch.object(self.service, 'cancel_push_mobile') as cancel_push:
            self.service._pstn_fallback('call-id')

        cancel_push.assert_not_called()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackCancelled
        )

    def test_pstn_fallback_originate_success_cancels_push(self):
        # Push must be cancelled only after a successful originate so that
        # both legs of the commit succeed or neither does.
        self._setup_eligible_fallback()

        with patch.object(self.service, 'cancel_push_mobile') as cancel_push:
            self.service._pstn_fallback('call-id')

        cancel_push.assert_called_once_with('call-id')
        self.ari_client.channels.originate.assert_called_once()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackDialing
        )

    def test_join_bridge_prunes_call_state(self):
        # Successful bridge creation should clean up per-call mapping dicts
        # so they don't grow unbounded.
        self.service._origin_call_id_by_bridge_uuid['bridge-uuid'] = 'call-id'
        self.service._bridge_uuid_by_origin_call_id['call-id'] = 'bridge-uuid'
        self.service._call_ring_time['call-id'] = 30
        self.service._incoming_calls['call-id'] = self._make_notified().received()
        dialer = Mock()
        self.service._contact_dialers['bridge-uuid'] = dialer
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'

        self.service.join_bridge('mobile-ch', 'bridge-uuid')

        assert 'bridge-uuid' not in self.service._origin_call_id_by_bridge_uuid
        assert 'call-id' not in self.service._bridge_uuid_by_origin_call_id
        assert 'call-id' not in self.service._call_ring_time
        assert 'bridge-uuid' not in self.service._caller_channel_leg_by_bridge
        assert 'call-id' not in self.service._incoming_calls

    def test_has_a_registered_mobile_and_pending_push_false_on_terminal_state(
        self,
    ):
        # Once a call reaches Received or Cancelled, it is no longer
        # considered to have a pending push.
        self.service._incoming_calls['call-id'] = self._make_notified().received()
        assert (
            self.service.has_a_registered_mobile_and_pending_push(
                'call-id', 'asterisk-call-id', 'PJSIP/aor', 'user-uuid'
            )
            is False
        )

        self.service._incoming_calls['call-id'] = self._make_notified().push_cancelled()
        assert (
            self.service.has_a_registered_mobile_and_pending_push(
                'call-id', 'asterisk-call-id', 'PJSIP/aor', 'user-uuid'
            )
            is False
        )

    def test_notify_channel_gone_prunes_call_state(self):
        caller_channel_id = '1234567890.42'
        dialed_channel_id = '1234567890.99'

        self.ari.client.channels.getChannelVar.return_value = {'value': 'pickupmark'}
        self.ari.client.channels.get.return_value = Mock(
            json={'caller': {'name': 'Test', 'number': '1001'}}
        )

        self.service.dial_all_contacts(caller_channel_id, 'call-id', 'aor')
        bridge_uuid = next(iter(self.service._contact_dialers))
        assert 'call-id' in self.service._bridge_uuid_by_origin_call_id

        dialer = self.service._contact_dialers[bridge_uuid]
        mock_dialed_channel = Mock()
        mock_dialed_channel.id = dialed_channel_id
        dialer._dialed_channels.add(mock_dialed_channel)
        dialer.stop()

        self.service.notify_channel_gone(dialed_channel_id)

        assert bridge_uuid not in self.service._origin_call_id_by_bridge_uuid
        assert 'call-id' not in self.service._bridge_uuid_by_origin_call_id
        assert 'call-id' not in self.service._call_ring_time
        assert bridge_uuid not in self.service._caller_channel_leg_by_bridge

    def test_on_calld_stopping_cancels_pstn_timers(self):
        timer_a = Mock()
        timer_b = Mock()
        self.service._pstn_fallbacks['call-a'] = PSTNFallbackPending(
            call_id='call-a', timer=timer_a
        )
        self.service._pstn_fallbacks['call-b'] = PSTNFallbackPending(
            call_id='call-b', timer=timer_b
        )

        self.service.on_calld_stopping()

        timer_a.cancel.assert_called_once()
        timer_b.cancel.assert_called_once()
        assert self.service._pstn_fallbacks == {}

    def test_cancel_pstn_fallback_transitions_pending_to_cancelled(self):
        timer = Mock()
        self.service._pstn_fallbacks['call-id'] = PSTNFallbackPending(
            call_id='call-id', timer=timer
        )
        self.service._call_locks['call-id'] = threading.RLock()

        self.service._cancel_pstn_fallback('call-id')

        timer.cancel.assert_called_once()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackCancelled
        )

    def test_pstn_fallback_noop_when_caller_channel_gone(self):
        self.service._incoming_calls['call-id'] = self._make_notified()
        self.service._bridge_uuid_by_origin_call_id['call-id'] = 'bridge-uuid'
        self.service._caller_channel_leg_by_bridge['bridge-uuid'] = 'caller-ch'
        self.confd_client.users.get.return_value = {
            'mobile_fallback_enabled': True,
            'mobile_phone_number': '+33123456789',
            'lines': [{'id': 42}],
        }
        self.confd_client.lines.get.return_value = {'context': 'my-outbound-context'}
        self.ari_client.channels.get.side_effect = ARINotFound(
            s.ari_client, s.original_error
        )

        self.service._pstn_fallback('call-id')

        self.ari_client.channels.originate.assert_not_called()

    def test_pstn_fallback_aborts_cleanly_when_caller_channel_lookup_fails(self):
        # ARI infrastructure failure (e.g. ARI down, network issue) during
        # the caller-channel presence check must abort the fallback cleanly
        # — push stays active, state transitions to Cancelled, Timer thread
        # does not die with an unhandled exception.
        self._setup_eligible_fallback()
        self.ari_client.channels.get.side_effect = requests.HTTPError()

        with patch.object(self.service, 'cancel_push_mobile') as cancel_push:
            self.service._pstn_fallback('call-id')

        cancel_push.assert_not_called()
        self.ari_client.channels.originate.assert_not_called()
        assert isinstance(
            self.service._pstn_fallbacks.get('call-id'), PSTNFallbackCancelled
        )
