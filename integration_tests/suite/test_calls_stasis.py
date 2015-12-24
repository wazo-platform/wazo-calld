# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_items
from xivo_test_helpers import until

from .base import IntegrationTest
from .base import MockChannel
from .base import MockLine
from .base import MockUser
from .base import MockUserLine


class TestDialedFrom(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestDialedFrom, self).setUp()
        self.reset_ari()
        self.reset_confd()

    def test_given_dialed_from_when_answer_then_the_two_are_talking(self):
        self.set_ari_channels(MockChannel(id='call-id'), MockChannel(id='new-call-id'))

        self.event_answer_connect(from_='call-id', new_call_id='new-call-id')

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
                'query': [['channel', 'call-id']],
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges/bridge-id/addChannel',
                'query': [['channel', 'new-call-id']],
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges',
                'query': [['type', 'mixing']],
            }))))

        until.assert_(assert_function, tries=5)

    def test_given_dialed_from_when_originator_hangs_up_then_user_stops_ringing(self):
        self.set_ari_channels(MockChannel(id='call-id'),
                              MockChannel(id='new-call-id', ))
        self.set_ari_channel_variable({'new-call-id': {'XIVO_USERID': 'user-id'}})
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id')]})
        self.set_ari_originates(MockChannel(id='new-call-id'))

        self.connect_user('call-id', 'user-id')

        self.event_hangup('call-id')

        def assert_function():
            assert_that(self.ari_requests(), has_entry('requests', has_items(has_entries({
                'method': 'DELETE',
                'path': '/ari/channels/new-call-id',
            }))))

        until.assert_(assert_function, tries=5)
