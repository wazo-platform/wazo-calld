# -*- coding: utf-8 -*-

# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import ari
import json
import logging

from hamcrest import all_of
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import equal_to
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import instance_of
from hamcrest import not_
from requests.exceptions import HTTPError

from xivo_test_helpers import until

from .test_api.base import IntegrationTest
from .test_api.constants import VALID_TOKEN
from .test_api.hamcrest_ import HamcrestARIBridge
from .test_api.hamcrest_ import HamcrestARIChannel

RECIPIENT = {
    'context': 'local',
    'exten': 'answer',
}
RECIPIENT_RINGING = {
    'context': 'local',
    'exten': 'ring',
}
RECIPIENT_RINGING_ANSWER = {
    'context': 'local',
    'exten': 'ringAnswer',
}
RECIPIENT_BUSY = {
    'context': 'local',
    'exten': 'busy',
}
RECIPIENT_NOT_FOUND = {
    'context': 'local',
    'exten': 'extenNotFound',
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
        self.b = HamcrestARIBridge(self.ari)
        self.c = HamcrestARIChannel(self.ari)

    def tearDown(self):
        self.clear_channels()

    def clear_channels(self):
        for channel in self.ari.channels.list():
            try:
                channel.hangup()
            except HTTPError:
                pass

    def given_bridged_call_stasis(self):
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

    def given_bridged_call_not_stasis(self):
        caller = self.ari.channels.originate(endpoint=ENDPOINT, context='local', extension='dial', priority=1)

        bridge = next(bridge for bridge in self.ari.bridges.list()
                      if caller.id in bridge.json['channels'])
        callee_id = next(channel_id for channel_id in bridge.json['channels']
                         if channel_id != caller.id)
        return caller.id, callee_id

    def given_ringing_transfer(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT_RINGING)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']

        return (transferred_channel_id,
                initiator_channel_id,
                recipient_channel_id,
                transfer_id)

    def given_ringing_and_answer_transfer(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT_RINGING_ANSWER)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']

        return (transferred_channel_id,
                initiator_channel_id,
                recipient_channel_id,
                transfer_id)

    def given_answered_transfer(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']

        def channel_is_in_bridge(channel_id, bridge_id):
            return channel_id in self.ari.bridges.get(bridgeId=bridge_id).json['channels']

        until.true(channel_is_in_bridge, recipient_channel_id, transfer_id, tries=3)

        return (transferred_channel_id,
                initiator_channel_id,
                recipient_channel_id,
                transfer_id)

    def assert_transfer_is_answered(self, transfer_id):
        try:
            transfer_bridge = self.ari.bridges.get(bridgeId=transfer_id)
        except HTTPError:
            raise AssertionError('no such bridge: id {}'.format(transfer_id))
        channel_ids = transfer_bridge.json['channels']
        assert_that(channel_ids, has_length(3))
        for channel_id in channel_ids:
            assert_that(channel_id, self.c.is_talking(), 'channel not talking')
            assert_that(channel_id, self.c.has_variable('XIVO_TRANSFER_ID', transfer_id), 'variable XIVO_TRANSFER_ID is wrong')
        transfer_roles = (self.ari.channels.getChannelVar(channelId=channel_id, variable='XIVO_TRANSFER_ROLE')['value']
                          for channel_id in transfer_bridge.json['channels'])
        assert_that(transfer_roles, contains_inanyorder('transferred', 'initiator', 'recipient'))
        transfer = self.ctid_ng.get_transfer(transfer_id)
        assert_that(transfer, has_entries({
            'id': transfer_id,
            'transferred_call': instance_of(unicode),
            'initiator_call': instance_of(unicode),
            'recipient_call': instance_of(unicode),
            'status': 'answered'
        }))
        cached_transfers = json.loads(self.ari.asterisk.getGlobalVar(variable='XIVO_TRANSFERS')['value'])
        assert_that(cached_transfers, has_length(1))

    def assert_transfer_is_cancelled(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id):
        transfer_bridge = self.ari.bridges.get(bridgeId=transfer_id)
        assert_that(transfer_bridge.json,
                    has_entry('channels',
                              contains_inanyorder(
                                  transferred_channel_id,
                                  initiator_channel_id
                              )))
        assert_that(transferred_channel_id, self.c.is_talking(), 'transferred channel not talking')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', ''), 'variable not unset')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', ''), 'variable not unset')

        assert_that(initiator_channel_id, self.c.is_talking(), 'initiator channel is not talking')
        assert_that(initiator_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', ''), 'variable not unset')
        assert_that(initiator_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', ''), 'variable not unset')

        assert_that(recipient_channel_id, self.c.is_hungup(), 'recipient channel is still talking')

        result = self.ctid_ng.get_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(result.status_code, equal_to(404))
        assert_that(self.ari.asterisk.getGlobalVar(variable='XIVO_TRANSFERS'), has_entry('value', '{}'))

    def assert_transfer_is_completed(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id):
        transfer_bridge = self.ari.bridges.get(bridgeId=transfer_id)
        assert_that(transfer_bridge.json,
                    has_entry('channels',
                              contains_inanyorder(
                                  transferred_channel_id,
                                  recipient_channel_id
                              )))
        assert_that(transferred_channel_id, self.c.is_talking(), 'transferred channel not talking')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', ''), 'variable not unset')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', ''), 'variable not unset')

        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')

        assert_that(recipient_channel_id, self.c.is_talking(), 'recipient channel not talking')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', ''), 'variable not unset')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', ''), 'variable not unset')

        result = self.ctid_ng.get_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(result.status_code, equal_to(404))
        assert_that(self.ari.asterisk.getGlobalVar(variable='XIVO_TRANSFERS'), has_entry('value', '{}'))

    def assert_transfer_is_abandoned(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id):
        transfer_bridge = self.ari.bridges.get(bridgeId=transfer_id)
        assert_that(transfer_bridge.json,
                    has_entry('channels',
                              contains_inanyorder(
                                  initiator_channel_id,
                                  recipient_channel_id
                              )))
        assert_that(transferred_channel_id, self.c.is_hungup(), 'transferred channel is still talking')

        assert_that(initiator_channel_id, self.c.is_talking(), 'initiator channel not talking')
        assert_that(initiator_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', ''), 'variable not unset')
        assert_that(initiator_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', ''), 'variable not unset')

        assert_that(recipient_channel_id, self.c.is_talking(), 'recipient channel not talking')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', ''), 'variable not unset')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', ''), 'variable not unset')

        result = self.ctid_ng.get_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(result.status_code, equal_to(404))
        assert_that(self.ari.asterisk.getGlobalVar(variable='XIVO_TRANSFERS'), has_entry('value', '{}'))

    def assert_transfer_is_hungup(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id):
        assert_that(transfer_id, not_(self.b.is_found()), 'transfer still exists')

        assert_that(transferred_channel_id, self.c.is_hungup(), 'transferred channel is still talking')
        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
        assert_that(recipient_channel_id, self.c.is_hungup(), 'recipient channel is still talking')

        result = self.ctid_ng.get_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(result.status_code, equal_to(404))
        assert_that(self.ari.asterisk.getGlobalVar(variable='XIVO_TRANSFERS'), has_entry('value', '{}'))


class TestTransferFromStasis(TestTransfers):

    def test_given_state_ready_when_transfer_start_and_answer_then_state_answered(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT)

        assert_that(response, all_of(has_entries({'transferred_call': transferred_channel_id,
                                                  'initiator_call': initiator_channel_id,
                                                  'status': 'ringback'}),
                                     has_key('id'),
                                     has_key('recipient_call')))

        transfer_id = response['id']

        until.assert_(self.assert_transfer_is_answered, transfer_id, tries=3)

    def test_given_state_ready_when_start_and_recipient_busy_then_state_cancelled(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT_BUSY)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_cancelled,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_ready_when_start_to_extension_not_found_then_state_cancelled(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT_NOT_FOUND)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_cancelled,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_ringback_when_cancel_then_state_cancelled(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_ringing_transfer()

        self.ctid_ng.cancel_transfer(transfer_id)

        until.assert_(self.assert_transfer_is_cancelled,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_ringback_when_recipient_hangup_then_state_cancelled(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_ringing_transfer()

        self.ari.channels.hangup(channelId=recipient_channel_id)

        until.assert_(self.assert_transfer_is_cancelled,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_ringback_when_transferred_hangup_and_recipient_answers_then_state_abandoned(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_ringing_and_answer_transfer()

        self.ari.channels.hangup(channelId=transferred_channel_id)

        until.assert_(self.assert_transfer_is_abandoned,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_ringback_when_transferred_hangup_and_recipient_hangup_then_state_hungup(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_ringing_transfer()

        self.ari.channels.hangup(channelId=transferred_channel_id)
        self.ari.channels.hangup(channelId=recipient_channel_id)

        until.assert_(self.assert_transfer_is_hungup,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_answered_when_complete_then_state_completed(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ctid_ng.complete_transfer(transfer_id)

        until.assert_(self.assert_transfer_is_completed,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_answered_when_cancel_then_state_cancelled(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ctid_ng.cancel_transfer(transfer_id)

        until.assert_(self.assert_transfer_is_cancelled,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_answered_when_recipient_hangup_then_state_cancelled(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ari.channels.hangup(channelId=recipient_channel_id)

        until.assert_(self.assert_transfer_is_cancelled,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_answered_when_initiator_hangup_then_state_completed(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ari.channels.hangup(channelId=initiator_channel_id)

        until.assert_(self.assert_transfer_is_completed,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_answered_when_transferred_hangup_then_state_abandoned(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ari.channels.hangup(channelId=transferred_channel_id)

        until.assert_(self.assert_transfer_is_abandoned,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_abandoned_when_initiator_hangup_then_everybody_hungup(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ari.channels.hangup(channelId=transferred_channel_id)

        until.assert_(self.assert_transfer_is_abandoned,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

        self.ari.channels.hangup(channelId=initiator_channel_id)

        until.assert_(self.assert_transfer_is_hungup,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

    def test_given_state_completed_when_recipient_hangup_then_everybody_hungup(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_answered_transfer()

        self.ctid_ng.complete_transfer(transfer_id)

        until.assert_(self.assert_transfer_is_completed,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)

        self.ari.channels.hangup(channelId=recipient_channel_id)

        until.assert_(self.assert_transfer_is_hungup,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=3)


class TestTransferFromNonStasis(TestTransfers):

    def test_given_state_ready_from_not_stasis_when_transfer_start_and_answer_then_state_answered(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis()

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT)

        assert_that(response, all_of(has_entries({'id': instance_of(unicode),
                                                  'transferred_call': transferred_channel_id,
                                                  'initiator_call': initiator_channel_id,
                                                  'recipient_call': None,
                                                  'status': 'starting'})))

        transfer_bridge_id = response['id']
        until.assert_(self.assert_transfer_is_answered, transfer_bridge_id, tries=3)
