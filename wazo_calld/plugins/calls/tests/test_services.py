# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, equal_to
from unittest.mock import Mock
from unittest import TestCase

from ..services import CallsService


class TestServices(TestCase):

    def setUp(self):
        self.services = CallsService(Mock(), Mock(), Mock(), Mock(), Mock(),
                                     Mock(), Mock())

        self.example_to_fit = {
            'type': 'ChannelDestroyed',
            'timestamp': '2021-06-15T11:06:46.331-0400',
            'cause': 3,
            'cause_txt': 'No route to destination',
            'channel': {
                'id': '1623769434.135',
                'name': 'PJSIP/HwnelF4k-00000075',
                'state': 'Up',
                'caller': {
                    'name': 'Oxynor',
                    'number': '9000'
                },
                'connected': {
                    'name': 'Xelanir',
                    'number': '9001'
                },
                'accountcode': '',
                'dialplan': {
                    'context': 'pickup',
                    'exten': 'my_pickup',
                    'priority': 3,
                    'app_name': '',
                    'app_data': ''
                },
                'creationtime': '2021-06-15T11:06'
                ':45.465-0400',
                'language': 'en_US',
                'channelvars':
                {
                    'CHANNEL(linkedid)': '1623743605.135',
                    'WAZO_CALL_RECORD_ACTIVE': '',
                    'WAZO_DEREFERENCED_USERUUID': '',
                    'WAZO_ENTRY_CONTEXT': 'default-key-2354-internal',
                    'WAZO_ENTRY_EXTEN': '9001',
                    'WAZO_LINE_ID': '2',
                    'WAZO_SIP_CALL_ID': 'coNsbzfk_Tcq2cffBi9g7Q..',
                    'WAZO_SWITCHBOARD_QUEUE': '',
                    'WAZO_SWITCHBOARD_HOLD': '',
                    'WAZO_TENANT_UUID': '6345gd34-9ac7-4337-818d-d04e606d9f74',
                    'XIVO_BASE_EXTEN': '9001',
                    'XIVO_ON_HOLD': '',
                    'XIVO_USERUUID': '76f7fmfh-a547-4324-a521-e2e04843cfee',
                    'WAZO_LOCAL_CHAN_MATCH_UUID': '',
                    'WAZO_CALL_RECORD_SIDE': 'caller',
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                }
            },
            'asterisk_id': '52:54:00:2a:da:g5',
            'application': 'callcontrol'
        }

    def test_given_no_chan_variables_when_make_call_from_stasis_event_then_call_has_none_values(self):
        event = self.example_to_fit
        event['channel']['channelvars'] = {}

        call = self.services.channel_destroyed_event(event)

        assert_that(call.user_uuid, equal_to(None))
        assert_that(call.dialed_extension, equal_to(None))

    def test_given_xivo_useruuid_when_make_call_from_stasis_event_then_call_has_useruuid(self):
        event = self.example_to_fit
        event['channel']['channelvars'] = {'XIVO_USERUUID': 'new_useruuid'}

        call = self.services.channel_destroyed_event(event)

        assert_that(call.user_uuid, equal_to('new_useruuid'))

    def test_given_wazo_dereferenced_useruuid_when_make_call_from_stasis_event_then_override_xivo_useruuid(self):
        event = self.example_to_fit
        event['channel']['channelvars'] = {
            'XIVO_USERUUID': 'my-user-uuid',
            'WAZO_DEREFERENCED_USERUUID': 'new-user-uuid',
        }

        call = self.services.channel_destroyed_event(event)

        assert_that(call.user_uuid, equal_to('new-user-uuid'))

    def test_creation_time_from_channel_creation_to_call_on_hungup(self):
        event = self.example_to_fit
        creation_time = event['channel']['creationtime']
        call = self.services.channel_destroyed_event(event)

        assert_that(call.creation_time, equal_to(creation_time))

    def test_direction_of_call_to_who_is_caller(self):
        event = self.example_to_fit
        call = self.services.channel_destroyed_event(event)

        assert_that(call.is_caller, equal_to(True))

    def _assert_conversation_direction(self, directions, expected):
        assert_that(
            self.services._conversation_direction_from_directions(directions),
            equal_to(expected),
        )

    def test_call_direction(self):

        inbound_channel = 'inbound'
        outbound_channel = 'outbound'
        internal_channel = 'internal'
        unknown_channel = 'unknown'

        self._assert_conversation_direction([], internal_channel)

        self._assert_conversation_direction([internal_channel], internal_channel)
        self._assert_conversation_direction([inbound_channel], inbound_channel)
        self._assert_conversation_direction([outbound_channel], outbound_channel)

        self._assert_conversation_direction([inbound_channel, inbound_channel], inbound_channel)
        self._assert_conversation_direction([inbound_channel, outbound_channel], unknown_channel)
        self._assert_conversation_direction([inbound_channel, internal_channel], inbound_channel)
        self._assert_conversation_direction([outbound_channel, inbound_channel], unknown_channel)
        self._assert_conversation_direction([outbound_channel, outbound_channel], outbound_channel)
        self._assert_conversation_direction([outbound_channel, internal_channel], outbound_channel)
        self._assert_conversation_direction([internal_channel, inbound_channel], inbound_channel)
        self._assert_conversation_direction([internal_channel, outbound_channel], outbound_channel)
        self._assert_conversation_direction([internal_channel, internal_channel], internal_channel)

        self._assert_conversation_direction([inbound_channel, inbound_channel, inbound_channel], inbound_channel)
        self._assert_conversation_direction([inbound_channel, outbound_channel, inbound_channel], unknown_channel)
        self._assert_conversation_direction([inbound_channel, internal_channel, internal_channel], inbound_channel)
        self._assert_conversation_direction([outbound_channel, inbound_channel, outbound_channel], unknown_channel)
        self._assert_conversation_direction([outbound_channel, outbound_channel, outbound_channel], outbound_channel)
        self._assert_conversation_direction([outbound_channel, internal_channel, internal_channel], outbound_channel)
        self._assert_conversation_direction([internal_channel, inbound_channel, internal_channel], inbound_channel)
        self._assert_conversation_direction([internal_channel, outbound_channel, internal_channel], outbound_channel)
        self._assert_conversation_direction([internal_channel, internal_channel, internal_channel], internal_channel)
