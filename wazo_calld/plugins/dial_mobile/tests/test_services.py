# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, patch
from unittest.mock import sentinel as s

import pytest
import requests
from ari.exceptions import ARINotFound
from hamcrest import assert_that, contains_exactly, empty, equal_to, has_items

from ..notifier import Notifier
from ..services import DialMobileService, _NoSuchChannel
from ..services import _PollingContactDialer as PollingContactDialer


class DialerTestCase(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.future_bridge_uuid = '6e2b692a-ff56-4121-932d-d208dd5c3362'
        self.aor = 'foobar'
        self.channel_id = '1234567890.42'
        self.ringing_time = 42
        self.pickup_mark = '1003%default'

        self.poller = PollingContactDialer(
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
        self.poller._dialed_channels = {channel_1, channel_2}  # type: ignore[assignment]

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
            channelId=self.poller._caller_channel_id
        )


class DialMobileServiceTestCase(DialerTestCase):
    def setUp(self):
        self.ari = Mock()
        self.ari.client = self.ari_client = Mock()
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.notifier = Mock(Notifier)
        self.service = DialMobileService(
            self.ari, self.notifier, self.amid_client, self.auth_client
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

    def test_join_bridge_unknown_future_bridge_will_hangup(self):
        with patch.object(self.service, 'cancel_push_mobile') as push_cancel:
            self.service.join_bridge(s.channel_id, s.bridge_uuid)
            push_cancel.assert_called_once_with(s.channel_id)

        self.ari_client.channels.hangup.assert_called_once_with(channelId=s.channel_id)

    def test_join_bridge_caller_gone_will_hangup(self):
        dialer = Mock()
        self.service._contact_dialers = {s.bridge_uuid: dialer}
        self.service._outgoing_calls = {s.bridge_uuid: s.caller_channel}
        self.ari_client.channels.answer.side_effect = ARINotFound(
            self.ari_client, s.error
        )

        with patch.object(self.service, 'cancel_push_mobile') as push_cancel:
            self.service.join_bridge(s.channel_id, s.bridge_uuid)
            push_cancel.assert_called_once_with(s.channel_id)

        dialer.stop.assert_called_once_with()

        self.ari_client.channels.hangup.assert_called_once_with(channelId=s.channel_id)


class TestCancelPushNotification(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.notifier = Mock(Notifier)
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.service = DialMobileService(
            self.ari, self.notifier, self.amid_client, self.auth_client
        )

    def test_that_nothing_happens_when_not_a_pending_push(self):
        self.service.cancel_push_mobile(s.call_id)

    def test_that_original_payload_is_sent_when_canceling(self):
        self.service.send_push_notification(
            s.tenant_uuid,
            s.user_uuid,
            s.call_id,
            s.sip_call_id,
            s.cid_name,
            s.cid_num,
            s.video_enabled,
            s.ring_timeout,
            s.origin_call_id,
            s.push_mobile_timestamp,
        )

        payload = self.notifier.push_notification.call_args_list[0][0][0]

        self.service.cancel_push_mobile(s.call_id)

        self.notifier.cancel_push_notification.assert_called_once_with(
            payload, s.tenant_uuid, s.user_uuid
        )
