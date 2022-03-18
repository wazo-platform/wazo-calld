# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
import requests

from mock import (
    Mock,
    patch,
    sentinel as s,
)
from hamcrest import (
    assert_that,
    contains_exactly,
    empty,
    equal_to,
    has_items,
)

from ari.exceptions import ARINotFound

from ..services import _PollingContactDialer as PollingContactDialer
from ..services import DialMobileService
from ..notifier import Notifier


class DialerTestCase(TestCase):

    def setUp(self):
        self.ari = Mock()
        self.future_bridge_uuid = '6e2b692a-ff56-4121-932d-d208dd5c3362'
        self.aor = 'foobar'
        self.channel_id = '1234567890.42'

        self.poller = PollingContactDialer(
            self.ari,
            self.future_bridge_uuid,
            self.channel_id,
            self.aor,
        )


class TestSendContactToCurrentCall(DialerTestCase):

    def test_sending_the_same_contact_twice(self):
        self.poller._send_contact_to_current_call(s.contact, self.future_bridge_uuid, s.caller_id)

        self.ari.reset_mock()

        self.poller._send_contact_to_current_call(s.contact, self.future_bridge_uuid, s.caller_id)

        self.ari.channels.originate.assert_not_called()

    def test_that_dialed_channels_are_tracked(self):
        self.poller._send_contact_to_current_call(s.contact, self.future_bridge_uuid, s.caller_id)

        assert_that(self.poller._dialed_channels, has_items(
            self.ari.channels.originate.return_value,
        ))

    def test_that_the_call_is_sent_to_dial_mobile_join(self):
        self.poller._send_contact_to_current_call(s.contact, self.future_bridge_uuid, s.caller_id)

        self.ari.channels.originate.assert_called_once_with(
            endpoint=s.contact,
            app='dial_mobile',
            appArgs=['join', self.future_bridge_uuid],
            callerId=s.caller_id,
            originator=self.channel_id,
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
        self.ari.channels.getChannelVar.side_effect = ARINotFound(s.ari_client, s.original_error)

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, empty())

    def test_one_value(self):
        self.ari.channels.getChannelVar.return_value = {'value': 'contact1'}

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, contains_exactly('contact1'))

    def test_multiple_values(self):
        self.ari.channels.getChannelVar.return_value = {'value': 'contact1&contact2&contact3'}

        result = self.poller._get_contacts(self.channel_id, self.aor)

        assert_that(result, contains_exactly('contact1', 'contact2', 'contact3'))


class TestRemoveUnansweredChannels(DialerTestCase):

    def test_that_hungup_channels_do_not_interrupt(self):
        channel_1 = Mock()
        channel_1.get.side_effect = ARINotFound(s.ari_client, s.original_error)

        channel_2 = Mock()
        channel_2.id = s.channel_2_id
        channel_2.get.return_value = Mock(json={'state': 'Ringing'})

        self.poller._dialed_channels = [channel_1, channel_2]

        self.poller._remove_unanswered_channels()

        self.ari.channels.hangup.assert_called_once_with(channelId=s.channel_2_id)

    def test_that_channels_hanging_up_during_the_execution_do_not_interrupt(self):
        channel_1 = Mock()
        channel_1.id = s.channel_1_id
        channel_1.get.return_value = Mock(json={'state': 'Ringing'})

        channel_2 = Mock()
        channel_2.id = s.channel_2_id
        channel_2.get.return_value = Mock(json={'state': 'Ringing'})

        self.poller._dialed_channels = [channel_1, channel_2]

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

        self.poller._dialed_channels = [channel_1]

        self.poller._remove_unanswered_channels()

        self.ari.channels.hangup.assert_called_with(channelId=s.channel_1_id)


class DialMobileServiceTestCase(DialerTestCase):

    def setUp(self):
        self.ari = Mock()
        self.amid_client = Mock()
        self.auth_client = Mock()
        self.notifier = Mock(Notifier)
        self.service = DialMobileService(self.ari, self.notifier, self.amid_client, self.auth_client)
        self.channel_id = '1234567890.42'
        self.aor = 'foobar'

    def test_that_caller_channel_rings(self):
        self.service.dial_all_contacts(self.channel_id, self.aor)

        self.ari.client.channels.ring.assert_called_once_with(channelId=self.channel_id)

    def test_set_user_hint_no_mobile_session(self):
        self.service._set_user_hint('<the-uuid>', False)

        self.amid_client.action.assert_called_once_with(
            'Setvar',
            {'Variable': 'DEVICE_STATE(Custom:<the-uuid>-mobile)', 'Value': 'UNAVAILABLE'},
        )

    def test_set_user_hint_with_mobile_session(self):
        self.service._set_user_hint('<the-uuid>', True)

        self.amid_client.action.assert_called_once_with(
            'Setvar',
            {'Variable': 'DEVICE_STATE(Custom:<the-uuid>-mobile)', 'Value': 'NOT_INUSE'},
        )

    def test_on_mobile_refresh_token_created(self):
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_created(s.user_uuid)
            mock.assert_called_once_with(s.user_uuid, True)

    def test_on_mobile_refresh_token_deleted(self):
        self.auth_client.token.list.return_value = {'items': [], 'filtered': 0, 'total': 42}
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_deleted(s.user_uuid)
            mock.assert_called_once_with(s.user_uuid, False)

        self.auth_client.token.list.return_value = {'items': [{'uuid': 'some-uuid'}], 'filtered': 1, 'total': 42}
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_deleted(s.user_uuid)
            mock.assert_called_once_with(s.user_uuid, True)

        self.auth_client.token.list.side_effect = requests.HTTPError()
        with patch.object(self.service, '_set_user_hint') as mock:
            self.service.on_mobile_refresh_token_deleted(s.user_uuid)
            mock.assert_not_called()
