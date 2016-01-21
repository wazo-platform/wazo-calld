# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_items
from xivo_test_helpers import until

from .test_api.base import IntegrationTest
from .test_api.ari import MockChannel
from .test_api.ctid_ng import new_call_id
from .test_api.confd import MockLine
from .test_api.confd import MockUser
from .test_api.confd import MockUserLine


class TestDialedFrom(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestDialedFrom, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_dialed_from_when_answer_then_the_two_are_talking(self):
        call_id = new_call_id()
        new_call_id_ = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id), MockChannel(id=new_call_id_))

        self.stasis.event_answer_connect(from_=call_id, new_call_id=new_call_id_)

        def assert_function():
            assert_that(self.ari.requests(), has_entry('requests', has_items(has_entries({
                'method': 'POST',
                'path': '/ari/channels/{channel_id}/answer'.format(channel_id=call_id),
            }), has_entries({
                'method': 'POST',
                'path': '/ari/channels/{channel_id}/answer'.format(channel_id=new_call_id_),
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges/bridge-id/addChannel',
                'query': [['channel', call_id]],
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges/bridge-id/addChannel',
                'query': [['channel', new_call_id_]],
            }), has_entries({
                'method': 'POST',
                'path': '/ari/bridges',
                'query': [['type', 'mixing']],
            }))))

        until.assert_(assert_function, tries=5)

    def test_given_dialed_from_when_originator_hangs_up_then_user_stops_ringing(self):
        call_id = new_call_id()
        new_call_id_ = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id),
                              MockChannel(id=new_call_id_, ))
        self.ari.set_channel_variable({new_call_id_: {'XIVO_USERUUID': 'user-uuid'}})
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        self.ari.set_originates(MockChannel(id=new_call_id_))

        self.ctid_ng.connect_user(call_id, 'user-uuid')

        self.stasis.event_hangup(call_id)

        def assert_function():
            assert_that(self.ari.requests(), has_entry('requests', has_items(has_entries({
                'method': 'DELETE',
                'path': '/ari/channels/{call_id}'.format(call_id=new_call_id_),
            }))))

        until.assert_(assert_function, tries=5)
