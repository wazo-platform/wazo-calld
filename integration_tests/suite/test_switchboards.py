# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import unittest

from ari.exceptions import ARINotInStasis
from hamcrest import assert_that
from hamcrest import contains
from hamcrest import contains_string
from hamcrest import contains_inanyorder
from hamcrest import empty
from hamcrest import equal_to
from hamcrest import has_entry
from hamcrest import is_not
from operator import attrgetter
from xivo_test_helpers import until

from .test_api.auth import MockUserToken
from .test_api.base import IntegrationTest
from .test_api.base import RealAsteriskIntegrationTest
from .test_api.constants import VALID_TOKEN
from .test_api.confd import MockSwitchboard
from .test_api.confd import MockLine
from .test_api.confd import MockUser
from .test_api.hamcrest_ import HamcrestARIChannel

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
STASIS_APP = 'callcontrol'
STASIS_APP_QUEUE = 'switchboard_queue'
UUID_NOT_FOUND = '99999999-9999-9999-9999-999999999999'
CALL_ID_NOT_FOUND = '99999999.99'


class TestSwitchboards(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super(TestSwitchboards, self).setUp()
        self.c = HamcrestARIChannel(self.ari)
        self.confd.reset()

    def channel_is_in_stasis(self, channel_id):
        try:
            self.ari.channels.setChannelVar(channelId=channel_id, variable='TEST_STASIS', value='')
            return True
        except ARINotInStasis:
            return False

    def channels_are_bridged(self, caller, callee):
        try:
            next(bridge for bridge in self.ari.bridges.list()
                 if (caller.id in bridge.json['channels'] and
                     callee.id in bridge.json['channels'] and
                     bridge.json['bridge_type'] == 'mixing'))
            return True
        except StopIteration:
            return False

    def latest_chantest_channel(self):
        chan_test_channels = [channel for channel in self.ari.channels.list()
                              if channel.json['name'].startswith('Test/')]
        return max(chan_test_channels, key=attrgetter('id'))


class TestSwitchboardCallsQueued(TestSwitchboards):

    def test_given_no_switchboard_then_404(self):
        result = self.ctid_ng.get_switchboard_queued_calls_result(UUID_NOT_FOUND, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_no_bridges_then_return_empty_list(self):
        for bridge in self.ari.bridges.list():
            bridge.delete()
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))

        calls = self.ctid_ng.switchboard_queued_calls(switchboard_uuid)

        assert_that(calls, has_entry('items', empty()))

    def test_given_one_call_hungup_then_return_empty_list(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        until.true(self.channel_is_in_stasis, new_channel.id, tries=2)
        new_channel.hangup()

        calls = self.ctid_ng.switchboard_queued_calls(switchboard_uuid)

        assert_that(calls, has_entry('items', empty()))

    def test_given_two_call_in_queue_then_list_two_calls(self):
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel_1 = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                    app=STASIS_APP,
                                                    appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        new_channel_2 = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                    app=STASIS_APP,
                                                    appArgs=[STASIS_APP_QUEUE, switchboard_uuid])

        def assert_function():
            calls = self.ctid_ng.switchboard_queued_calls(switchboard_uuid)
            assert_that(calls, has_entry('items', contains_inanyorder(has_entry('id', new_channel_1.id),
                                                                      has_entry('id', new_channel_2.id))))

        until.assert_(assert_function, tries=3)

    def test_given_no_calls_when_new_queued_call_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])

        def event_received():
            assert_that(bus_events.accumulate(),
                        contains(has_entry('data',
                                           has_entry('items',
                                                     contains(has_entry('id',
                                                                        new_channel.id))))))

        until.assert_(event_received, tries=3)

    def test_given_one_call_queued_when_hangup_then_bus_event(self):
        switchboard_uuid = 'my-switchboard-uuid'
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])

        until.true(bus_events.accumulate, tries=3)

        new_channel.hangup()

        def event_received():
            assert_that(bus_events.accumulate(),
                        contains(has_entry('data',
                                           has_entry('items',
                                                     is_not(empty()))),
                                 has_entry('data',
                                           has_entry('items',
                                                     empty()))))

        until.assert_(event_received, tries=3)

    @unittest.skip
    def test_given_one_call_queued_answered_held_when_unhold_then_no_queued_calls_updated_bus_event(self):
        '''
        To be implemented when holding calls will be possible, testing that
        WAZO_SWITCHBOARD_QUEUE is reset correctly when leaving the queue
        '''
        pass


class TestSwitchboardCallsQueuedAnswer(TestSwitchboards):

    def test_given_no_switchboard_when_answer_then_404(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        switchboard_uuid = UUID_NOT_FOUND
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        caller_call_id = new_channel.id

        result = self.ctid_ng.put_switchboard_queued_call_answer_result(switchboard_uuid, caller_call_id, token)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('switchboard'))

    def test_given_no_queued_call_when_answer_then_404(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))

        result = self.ctid_ng.put_switchboard_queued_call_answer_result(switchboard_uuid, CALL_ID_NOT_FOUND, token)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('call'))

    def test_given_token_with_no_user_when_answer_then_400(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        caller_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)

        result = self.ctid_ng.put_switchboard_queued_call_answer_result(switchboard_uuid, caller_call_id, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_given_operator_has_no_line_when_answer_then_400(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        caller_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)

        result = self.ctid_ng.put_switchboard_queued_call_answer_result(switchboard_uuid, caller_call_id, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('line'))

    def test_given_one_queued_call_and_one_operator_when_answer_then_operator_is_bridged(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator/autoanswer', protocol='test'))
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        caller_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)

        self.ctid_ng.switchboard_answer_queued_call(switchboard_uuid, caller_call_id, token)

        operator_channel = self.latest_chantest_channel()
        until.true(self.channels_are_bridged, operator_channel, new_channel, tries=3)

    def test_given_operator_is_answering_a_hungup_channel_when_answer_then_operator_is_hungup(self):
        token = 'my-token'
        user_uuid = 'my-user-uuid'
        line_id = 'my-line-id'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        switchboard_uuid = 'my-switchboard-uuid'
        self.confd.set_switchboards(MockSwitchboard(uuid=switchboard_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='switchboard-operator', protocol='test'))
        bus_events = self.bus.accumulator('switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_QUEUE, switchboard_uuid])
        caller_call_id = new_channel.id
        until.true(bus_events.accumulate, tries=3)
        self.ctid_ng.switchboard_answer_queued_call(switchboard_uuid, caller_call_id, token)
        new_channel.hangup()

        operator_channel = self.latest_chantest_channel()

        self.chan_test.answer_channel(operator_channel)

        def operator_is_hungup():
            assert_that(operator_channel.id, self.c.is_hungup())

        until.assert_(operator_is_hungup, tries=3)


class TestSwitchboardNoConfd(IntegrationTest):

    asset = 'no_confd'

    def test_given_no_confd_when_list_queued_calls_then_503(self):
        result = self.ctid_ng.get_switchboard_queued_calls_result(UUID_NOT_FOUND, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))
