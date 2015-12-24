# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_item
from hamcrest import has_items
from xivo_test_helpers import until

from .base import IntegrationTest
from .base import MockChannel
from .base import MockLine
from .base import MockUser
from .base import MockUserLine
from .base import XIVO_UUID


class TestDialedFrom(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestDialedFrom, self).setUp()
        self.reset_ari()
        self.reset_confd()

    def test_given_dialed_from_when_answer_then_the_two_are_talking(self):
        call_id = self.new_call_id()
        new_call_id = self.new_call_id()
        self.set_ari_channels(MockChannel(id=call_id), MockChannel(id=new_call_id))

        self.event_answer_connect(from_=call_id, new_call_id=new_call_id)

        def assert_function():
            assert_that(self.ari_requests(), has_entry('requests', has_items(has_entries({
                'method': 'POST',
                'path': '/ari/channels/{channel_id}/answer'.format(channel_id=call_id),
            }), has_entries({
                'method': 'POST',
                'path': '/ari/channels/{channel_id}/answer'.format(channel_id=new_call_id),
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges/bridge-id/addChannel',
                'query': [['channel', call_id]],
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges/bridge-id/addChannel',
                'query': [['channel', new_call_id]],
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges',
                'query': [['type', 'mixing']],
            }))))

        until.assert_(assert_function, tries=5)

    def test_given_dialed_from_when_originator_hangs_up_then_user_stops_ringing(self):
        call_id = self.new_call_id()
        new_call_id = self.new_call_id()
        self.set_ari_channels(MockChannel(id=call_id),
                              MockChannel(id=new_call_id, ))
        self.set_ari_channel_variable({new_call_id: {'XIVO_USERID': 'user-id'}})
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id')]})
        self.set_ari_originates(MockChannel(id=new_call_id))

        self.connect_user(call_id, 'user-id')

        self.event_hangup(call_id)

        def assert_function():
            assert_that(self.ari_requests(), has_entry('requests', has_items(has_entries({
                'method': 'DELETE',
                'path': '/ari/channels/{call_id}'.format(call_id=new_call_id),
            }))))

        until.assert_(assert_function, tries=5)

    def test_when_channel_ended_then_bus_event(self):
        call_id = self.new_call_id()
        self.set_ari_channels(MockChannel(id=call_id))
        self.listen_bus_events(routing_key='calls.call.ended')

        self.event_hangup(call_id)

        def assert_function():
            assert_that(self.bus_events(), has_item(has_entries({
                'name': 'call_ended',
                'origin_uuid': XIVO_UUID,
                'data': has_entry('call_id', call_id)
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_created_then_bus_event(self):
        call_id = self.new_call_id()
        self.set_ari_channels(MockChannel(id=call_id))
        self.listen_bus_events(routing_key='calls.call.created')

        self.event_new_channel(call_id)

        def assert_function():
            assert_that(self.bus_events(), has_item(has_entries({
                'name': 'call_created',
                'origin_uuid': XIVO_UUID,
                'data': has_entry('call_id', call_id)
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_updated_then_bus_event(self):
        call_id = self.new_call_id()
        self.set_ari_channels(MockChannel(id=call_id, state='Ring'))
        self.listen_bus_events(routing_key='calls.call.updated')

        self.event_channel_updated(call_id, state='Up')

        def assert_function():
            assert_that(self.bus_events(), has_item(has_entries({
                'name': 'call_updated',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id, 'status': 'Up'})
            })))

        until.assert_(assert_function, tries=5)
