# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_items
from xivo_test_helpers import until

from .helpers.ari_ import MockChannel
from .helpers.base import IntegrationTest
from .helpers.constants import STASIS_APP_NAME
from .helpers.constants import STASIS_APP_INSTANCE_NAME
from .helpers.ctid_ng import new_call_id
from .helpers.confd import MockLine
from .helpers.confd import MockUser


class TestDialedFrom(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_dialed_from_when_answer_then_the_two_are_talking(self):
        call_id = new_call_id()
        new_call_id_ = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id), MockChannel(id=new_call_id_))
        self.ari.set_global_variables({'XIVO_CHANNELS_{}'.format(call_id): json.dumps({'state': 'ringing',
                                                                                       'app': STASIS_APP_NAME,
                                                                                       'app_instance': STASIS_APP_INSTANCE_NAME})})

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
        call_id = 'call-id'
        new_call_id = 'new-call-id'
        self.ari.set_channels(MockChannel(id=call_id),
                              MockChannel(id=new_call_id, ))
        self.ari.set_channel_variable({new_call_id: {'XIVO_USERUUID': 'user-uuid'}})
        self.ari.set_global_variables({'XIVO_CHANNELS_{}'.format(call_id): json.dumps({'app': 'my-app',
                                                                                       'app_instance': 'sw1',
                                                                                       'state': 'ringing'})})
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='pjsip'))
        self.ari.set_originates(MockChannel(id=new_call_id))

        self.ctid_ng.connect_user(call_id, 'user-uuid')

        self.stasis.event_hangup(call_id)

        def assert_function():
            assert_that(self.ari.requests(), has_entry('requests', has_items(has_entries({
                'method': 'DELETE',
                'path': '/ari/channels/{call_id}'.format(call_id=new_call_id),
            }))))

        until.assert_(assert_function, tries=5)
