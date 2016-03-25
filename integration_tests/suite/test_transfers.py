# -*- coding: utf-8 -*-

# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import ari
import logging

from hamcrest import all_of
from hamcrest import assert_that
from hamcrest import is_in
from hamcrest import has_entries
from hamcrest import has_key

from xivo_test_helpers import until

from .test_api.base import IntegrationTest

RECIPIENT = {
    'context': 'local',
    'exten': 'answer',
}
ENDPOINT = 'Local/answer@local'
STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'integration-tests'
ARI_CONFIG = {
    'base_url': 'http://localhost:5039',
    'username': 'xivo',
    'password': 'xivo',
}

logging.getLogger('swaggerpy.client').setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)


class TestTransfers(IntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super(TestTransfers, self).setUp()
        self.ari = ari.connect(**ARI_CONFIG)

    def is_in_bridge(self, type_=None):
        bridges = self.ari.bridges.list()
        if type_:
            bridges = (bridge for bridge in bridges if bridge.json['bridge_type'] == type_)
        channel_ids = (channel_id for bridge in bridges for channel_id in bridge.json['channels'])
        return is_in(list(channel_ids))

    def is_talking_to(self, channel_id):
        bridges = self.ari.bridges.list()
        bridges = (bridge for bridge in bridges
                   if (channel_id in bridge.json['channels'] and
                       bridge.json['bridge_type'] == 'mixing'))
        channel_ids = (channel_id for bridge in bridges for channel_id in bridge.json['channels'])
        return is_in(channel_ids)

    def is_talking(self):
        channels = self.ari.channels.list()
        channel_ids = (channel.id for channel in channels if channel.json['state'] == 'Up')
        return is_in(list(channel_ids))

    def bridged_call_stasis(self):
        caller = self.ari.channels.originate(endpoint=ENDPOINT,
                                             app=STASIS_APP,
                                             variables={'variables': {'XIVO_STASIS_ARGS': STASIS_APP_INSTANCE}})
        callee = self.ari.channels.originate(endpoint=ENDPOINT,
                                             app=STASIS_APP,
                                             variables={'variables': {'XIVO_STASIS_ARGS': STASIS_APP_INSTANCE}})
        bridge = self.ari.bridges.create(type='mixing')

        def channel_is_up(channel_id):
            return self.ari.channels.get(channelId=channel_id).json['state'] == 'Up'

        until.true(channel_is_up, caller.id)
        bridge.addChannel(channel=caller.id)
        until.true(channel_is_up, callee.id)
        bridge.addChannel(channel=callee.id)
        return caller.id, callee.id

    def test_given_state_ready_when_transfer_start_and_answer_then_state_answered(self):
        transferred_channel_id, initiator_channel_id = self.bridged_call_stasis()

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT)

        assert_that(response, all_of(has_entries({'transferred_call': transferred_channel_id,
                                                  'initiator_call': initiator_channel_id,
                                                  'context': RECIPIENT['context'],
                                                  'exten': RECIPIENT['exten']}),
                                     has_key('uuid'),
                                     has_key('recipient_call')))

        recipient_channel_id = response['recipient_call']

        def transfer_is_answered():
            assert_that(transferred_channel_id, self.is_in_bridge(type_='holding'), 'transferred not holding')
            assert_that(initiator_channel_id, self.is_in_bridge(type_='mixing'), 'initiator not mixing')
            assert_that(initiator_channel_id, self.is_talking_to(recipient_channel_id), 'initiator not talking to')
            assert_that(recipient_channel_id, self.is_talking(), 'recipient channel not talking')

        until.assert_(transfer_is_answered, tries=3)
