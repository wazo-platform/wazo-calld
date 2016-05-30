# -*- coding: utf-8 -*-

# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import ari
import logging

from ari.exceptions import ARINotFound
from ari.exceptions import ARINotInStasis

from hamcrest import all_of
from hamcrest import anything
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import contains_string
from hamcrest import equal_to
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import has_item
from hamcrest import has_key
from hamcrest import instance_of
from hamcrest import not_

from xivo_test_helpers import until

from .test_api.base import IntegrationTest
from .test_api.constants import VALID_TOKEN
from .test_api.hamcrest_ import HamcrestARIBridge
from .test_api.hamcrest_ import HamcrestARIChannel

ARI_CONFIG = {
    'base_url': 'http://localhost:5039',
    'username': 'xivo',
    'password': 'xivo',
}
ENDPOINT = 'Local/answer@local'
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
RECIPIENT_CALLER_ID = {
    'context': 'local',
    'exten': 'answer-caller-id',
}
SOME_CHANNEL_ID = '123456789.123'
SOME_TRANSFER_ID = '123456789.123'
STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'integration-tests'

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
            except ARINotFound:
                pass

    def given_bridged_call_stasis(self):
        caller = self.ari.channels.originate(endpoint=ENDPOINT,
                                             app=STASIS_APP,
                                             appArgs=[STASIS_APP_INSTANCE])
        callee = self.ari.channels.originate(endpoint=ENDPOINT,
                                             app=STASIS_APP,
                                             appArgs=[STASIS_APP_INSTANCE])
        bridge = self.ari.bridges.create(type='mixing')

        def channel_is_in_stasis(channel_id):
            try:
                self.ari.channels.setChannelVar(channelId=channel_id, variable='TEST_STASIS', value='')
                return True
            except ARINotInStasis:
                return False

        until.true(channel_is_in_stasis, caller.id, tries=2)
        bridge.addChannel(channel=caller.id)
        until.true(channel_is_in_stasis, callee.id, tries=2)
        bridge.addChannel(channel=callee.id)
        return caller.id, callee.id

    def given_bridged_call_not_stasis(self):
        caller = self.ari.channels.originate(endpoint=ENDPOINT, context='local', extension='dial', priority=1)

        def channels_are_talking(caller_channel_id):
            try:
                bridge = next(bridge for bridge in self.ari.bridges.list()
                              if caller.id in bridge.json['channels'])
                callee_id = next(channel_id for channel_id in bridge.json['channels']
                                 if channel_id != caller_channel_id)
                return callee_id
            except StopIteration:
                return None

        callee_id = until.true(channels_are_talking, caller.id, tries=2)
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

        until.true(channel_is_in_bridge, recipient_channel_id, transfer_id, tries=5)

        return (transferred_channel_id,
                initiator_channel_id,
                recipient_channel_id,
                transfer_id)

    def assert_transfer_is_answered(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id=None):
        transfer = self.ctid_ng.get_transfer(transfer_id)
        assert_that(transfer, has_entries({
            'id': transfer_id,
            'transferred_call': transferred_channel_id,
            'initiator_call': initiator_channel_id,
            'recipient_call': (recipient_channel_id if recipient_channel_id else anything()),
            'status': 'answered'
        }))

        recipient_channel_id = transfer['recipient_call']

        try:
            transfer_bridge = self.ari.bridges.get(bridgeId=transfer_id)
        except ARINotFound:
            raise AssertionError('no transfer bridge')
        assert_that(transfer_bridge.json,
                    has_entry('channels',
                              contains_inanyorder(
                                  transferred_channel_id,
                                  initiator_channel_id,
                                  recipient_channel_id,
                              )))

        assert_that(transferred_channel_id, self.c.is_talking(), 'transferred channel not talking')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', transfer_id), 'variable not set')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', 'transferred'), 'variable not set')

        assert_that(initiator_channel_id, self.c.is_talking(), 'initiator channel is not talking')
        assert_that(initiator_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', transfer_id), 'variable not set')
        assert_that(initiator_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', 'initiator'), 'variable not set')

        assert_that(recipient_channel_id, self.c.is_talking(), 'recipient channel is not talking')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', transfer_id), 'variable not set')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', 'recipient'), 'variable not set')

        assert_that(self.bus.events(), has_item(has_entry('name', 'transfer_answered')))

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
        assert_that(result.status_code, equal_to(404), 'transfer not removed')

        events = self.bus.events()
        assert_that(events, has_item(has_entry('name', 'transfer_cancelled')))
        assert_that(events, has_item(has_entry('name', 'transfer_ended')))

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

        events = self.bus.events()
        assert_that(events, has_item(has_entry('name', 'transfer_answered')))
        assert_that(events, has_item(has_entry('name', 'transfer_completed')))
        assert_that(events, has_item(has_entry('name', 'transfer_ended')))

    def assert_transfer_is_blind_transferred(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id=None):
        transfer = self.ctid_ng.get_transfer(transfer_id)
        assert_that(transfer, has_entries({
            'id': transfer_id,
            'transferred_call': transferred_channel_id,
            'initiator_call': initiator_channel_id,
            'recipient_call': (recipient_channel_id if recipient_channel_id else anything()),
            'status': 'blind_transferred',
        }))

        recipient_channel_id = transfer['recipient_call']

        transfer_bridge = self.ari.bridges.get(bridgeId=transfer_id)
        assert_that(transfer_bridge.json,
                    has_entry('channels',
                              contains_inanyorder(
                                  transferred_channel_id,
                              )))
        assert_that(transferred_channel_id, self.c.is_ringback(), 'transferred channel not ringing')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', transfer_id), 'variable not set')
        assert_that(transferred_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', 'transferred'), 'variable not set')

        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')

        assert_that(recipient_channel_id, self.c.is_ringing(), 'recipient channel not ringing')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ID', transfer_id), 'variable not set')
        assert_that(recipient_channel_id, self.c.has_variable('XIVO_TRANSFER_ROLE', 'recipient'), 'variable not set')

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

        events = self.bus.events()
        assert_that(events, has_item(has_entry('name', 'transfer_abandoned')))
        assert_that(events, has_item(has_entry('name', 'transfer_ended')))

    def assert_transfer_is_hungup(self, transfer_id, transferred_channel_id, initiator_channel_id, recipient_channel_id):
        assert_that(transfer_id, not_(self.b.is_found()), 'transfer still exists')

        assert_that(transferred_channel_id, self.c.is_hungup(), 'transferred channel is still talking')
        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
        assert_that(recipient_channel_id, self.c.is_hungup(), 'recipient channel is still talking')

        result = self.ctid_ng.get_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(result.status_code, equal_to(404))

        assert_that(self.bus.events(), has_item(has_entry('name', 'transfer_ended')))

    def assert_everyone_hungup(self, transferred_channel_id, initiator_channel_id, recipient_channel_id):
        assert_that(transferred_channel_id, self.c.is_hungup(), 'transferred channel is still talking')
        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
        assert_that(recipient_channel_id, self.c.is_hungup(), 'recipient channel is still talking')


class TestCreateTransfer(TestTransfers):

    def test_given_invalid_input_when_create_then_error_400(self):
        for invalid_body in self.invalid_transfer_requests():
            response = self.ctid_ng.post_transfer_result(invalid_body, VALID_TOKEN)

            assert_that(response.status_code, equal_to(400))
            assert_that(response.json(), has_entry('message', contains_string('invalid')))

    def invalid_transfer_requests(self):
        valid_transfer_request = {
            'transferred_call': 'some-channel-id',
            'initiator_call': 'some-channel-id',
            'context': 'some-context',
            'exten': 'some-extension'
        }

        for key in ('transferred_call', 'initiator_call', 'context', 'exten'):
            body = dict(valid_transfer_request)
            body.pop(key)
            yield body
            body[key] = None
            yield body
            body[key] = 1234
            yield body
            body[key] = True
            yield body
            body[key] = ''
            yield body

    def test_given_transferred_not_found_when_create_then_error_400(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        body = {
            'transferred_call': 'not-found',
            'initiator_call': initiator_channel_id,
        }
        body.update(RECIPIENT)

        response = self.ctid_ng.post_transfer_result(body, VALID_TOKEN)

        assert_that(response.status_code, equal_to(400))
        assert_that(response.json(), has_entry('message', contains_string('creation')))

    def test_given_initiator_not_found_when_create_then_error_400(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        body = {
            'transferred_call': transferred_channel_id,
            'initiator_call': 'not-found',
        }
        body.update(RECIPIENT)

        response = self.ctid_ng.post_transfer_result(body, VALID_TOKEN)

        assert_that(response.status_code, equal_to(400))
        assert_that(response.json(), has_entry('message', contains_string('creation')))

    def test_given_recipient_not_found_when_create_then_error_400(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        body = {
            'transferred_call': transferred_channel_id,
            'initiator_call': initiator_channel_id,
        }
        body.update(RECIPIENT_NOT_FOUND)

        response = self.ctid_ng.post_transfer_result(body, VALID_TOKEN)

        assert_that(response.status_code, equal_to(400))
        assert_that(response.json(), has_entries({'message': contains_string('extension'),
                                                  'details': has_entries({'exten': RECIPIENT_NOT_FOUND['exten'],
                                                                          'context': RECIPIENT_NOT_FOUND['context']})}))

    def test_given_stasis_when_create_then_event_sent_in_bus(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        self.bus.listen_events('calls.transfer.created')
        self.ctid_ng.create_transfer(transferred_channel_id,
                                     initiator_channel_id,
                                     **RECIPIENT)

        def event_is_sent():
            assert_that(self.bus.events(), has_item(has_entry('name', 'transfer_created')))

        until.assert_(event_is_sent, tries=5)

    def test_given_non_stasis_when_create_then_event_sent_in_bus(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis()

        self.bus.listen_events('calls.transfer.created')
        self.ctid_ng.create_transfer(transferred_channel_id,
                                     initiator_channel_id,
                                     **RECIPIENT)

        def event_is_sent():
            assert_that(self.bus.events(), has_item(has_entry('name', 'transfer_created')))

        until.assert_(event_is_sent, tries=5)

    def test_when_create_then_caller_ids_are_right(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        initiator_caller_id_name = u'înîtîâtôr'
        recipient_caller_id_name = u'rêcîpîênt'
        self.ari.channels.setChannelVar(channelId=initiator_channel_id, variable='CALLERID(name)', value=initiator_caller_id_name.encode('utf-8'))

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT_CALLER_ID)

        def caller_id_are_right():
            recipient_channel = self.ari.channels.get(channelId=response['recipient_call'])
            assert_that(recipient_channel.json['connected']['name'], equal_to(initiator_caller_id_name))

            initiator_channel = self.ari.channels.get(channelId=initiator_channel_id)
            assert_that(initiator_channel.json['connected']['name'], equal_to(recipient_caller_id_name))

        until.assert_(caller_id_are_right, tries=5)

    def test_when_create_blind_transfer_then_caller_ids_are_right(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        transferred_caller_id_name = u'trânsfêrrêd'
        initiator_caller_id_name = u'înîtîâtôr'
        recipient_caller_id_name = u'rêcîpîênt'
        self.ari.channels.setChannelVar(channelId=initiator_channel_id, variable='CALLERID(name)', value=initiator_caller_id_name.encode('utf-8'))
        self.ari.channels.setChannelVar(channelId=transferred_channel_id, variable='CALLERID(name)', value=transferred_caller_id_name.encode('utf-8'))

        self.ctid_ng.create_blind_transfer(transferred_channel_id,
                                           initiator_channel_id,
                                           **RECIPIENT_CALLER_ID)

        def caller_id_are_right():
            transferred_channel = self.ari.channels.get(channelId=transferred_channel_id)
            assert_that(transferred_channel.json['connected']['name'], equal_to(recipient_caller_id_name))

        until.assert_(caller_id_are_right, tries=5)

    def test_given_no_content_type_when_create_then_ok(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        body = {
            'transferred_call': transferred_channel_id,
            'initiator_call': initiator_channel_id,
        }
        body.update(RECIPIENT)

        with self.ctid_ng.send_no_content_type():
            response = self.ctid_ng.post_transfer_result(body=body, token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(201))


class TestGetTransfer(TestTransfers):

    def test_given_no_transfer_when_get_then_error_404(self):
        response = self.ctid_ng.get_transfer_result(transfer_id='not-found', token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(404))


class TestCancelTransfer(TestTransfers):

    def test_given_no_transfer_when_cancel_transfer_then_error_404(self):
        response = self.ctid_ng.delete_transfer_result(transfer_id='not-found', token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(404))


class TestCompleteTransfer(TestTransfers):

    def test_given_no_transfer_when_complete_transfer_then_error_404(self):
        response = self.ctid_ng.put_complete_transfer_result(transfer_id='not-found', token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(404))


class TestTransferFromStasis(TestTransfers):

    def setUp(self):
        super(TestTransferFromStasis, self).setUp()
        self.bus.listen_events('calls.transfer.*')

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
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_answered,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

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
                      tries=5)

    def test_given_state_ready_when_blind_transfer_then_state_blind_transferred(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_blind_transfer(transferred_channel_id,
                                                      initiator_channel_id,
                                                      **RECIPIENT_RINGING)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_blind_transferred,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

    def test_given_state_ready_when_transfer_and_initiator_hangup_then_state_blind_transferred(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_transfer(transferred_channel_id,
                                                initiator_channel_id,
                                                **RECIPIENT_RINGING)

        self.ari.channels.hangup(channelId=initiator_channel_id)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_blind_transferred,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

    def test_given_state_ready_when_blind_transfer_and_answer_then_state_completed(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_blind_transfer(transferred_channel_id,
                                                      initiator_channel_id,
                                                      **RECIPIENT)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_completed,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

    def test_given_state_ready_when_blind_transfer_and_abandon_then_state_hungup(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_stasis()

        response = self.ctid_ng.create_blind_transfer(transferred_channel_id,
                                                      initiator_channel_id,
                                                      **RECIPIENT_RINGING)

        self.ari.channels.hangup(channelId=transferred_channel_id)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_hungup,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

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
                      tries=5)

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
                      tries=5)

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
                      tries=5)

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
                      tries=5)

    def test_given_state_ringback_when_transferred_hangup_and_initiator_hangup_then_state_hungup(self):
        (transferred_channel_id,
         initiator_channel_id,
         recipient_channel_id,
         transfer_id) = self.given_ringing_transfer()

        self.ari.channels.hangup(channelId=transferred_channel_id)
        self.ari.channels.hangup(channelId=initiator_channel_id)

        until.assert_(self.assert_transfer_is_hungup,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

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
                      tries=5)

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
                      tries=5)

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
                      tries=5)

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
                      tries=5)

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
                      tries=5)

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
                      tries=5)

        self.ari.channels.hangup(channelId=initiator_channel_id)

        until.assert_(self.assert_everyone_hungup,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

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
                      tries=5)

        self.ari.channels.hangup(channelId=recipient_channel_id)

        until.assert_(self.assert_everyone_hungup,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)

    def test_that_XIVO_TRANSFER_TARGET_is_not_reset_for_other_transfers(self):
        (transferred_channel_id1,
         initiator_channel_id1,
         recipient_channel_id1,
         transfer_id1) = self.given_ringing_and_answer_transfer()

        (transferred_channel_id2,
         initiator_channel_id2,
         recipient_channel_id2,
         transfer_id2) = self.given_ringing_transfer()

        until.assert_(self.assert_transfer_is_answered,
                      transfer_id1,
                      transferred_channel_id1,
                      initiator_channel_id1,
                      recipient_channel_id1,
                      tries=5)

        self.ari.channels.hangup(channelId=transferred_channel_id2)
        self.ari.channels.hangup(channelId=initiator_channel_id2)

        until.assert_(self.assert_transfer_is_hungup,
                      transfer_id2,
                      transferred_channel_id2,
                      initiator_channel_id2,
                      recipient_channel_id2,
                      tries=5)


class TestTransferFromNonStasis(TestTransfers):

    def setUp(self):
        super(TestTransferFromNonStasis, self).setUp()
        self.bus.listen_events('calls.transfer.*')

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
        until.assert_(self.assert_transfer_is_answered,
                      transfer_bridge_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      tries=5)

    def test_given_state_ready_when_blind_transfer_then_state_blind_transferred(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis()

        response = self.ctid_ng.create_blind_transfer(transferred_channel_id,
                                                      initiator_channel_id,
                                                      **RECIPIENT_RINGING)

        transfer_id = response['id']
        recipient_channel_id = response['recipient_call']
        until.assert_(self.assert_transfer_is_blind_transferred,
                      transfer_id,
                      transferred_channel_id,
                      initiator_channel_id,
                      recipient_channel_id,
                      tries=5)


class TestTransferFailingARI(IntegrationTest):

    asset = 'failing_ari'

    def test_given_no_ari_when_transfer_start_then_error_503(self):
        transferred_channel_id = SOME_CHANNEL_ID
        initiator_channel_id = SOME_CHANNEL_ID
        body = {
            'transferred_call': transferred_channel_id,
            'initiator_call': initiator_channel_id,
        }
        body.update(RECIPIENT)
        response = self.ctid_ng.post_transfer_result(body, token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(503))
        assert_that(response.json(), has_entry('message', contains_string('ARI')))

    def test_given_no_ari_when_get_transfer_then_error_503(self):
        response = self.ctid_ng.get_transfer_result(SOME_TRANSFER_ID, token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(503))
        assert_that(response.json(), has_entry('message', contains_string('ARI')))

    def test_given_no_ari_when_delete_transfer_then_error_503(self):
        response = self.ctid_ng.delete_transfer_result(SOME_TRANSFER_ID, token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(503))
        assert_that(response.json(), has_entry('message', contains_string('ARI')))

    def test_given_no_ari_when_complete_transfer_then_error_503(self):
        response = self.ctid_ng.put_complete_transfer_result(SOME_TRANSFER_ID, token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(503))
        assert_that(response.json(), has_entry('message', contains_string('ARI')))


class TestNoAmid(TestTransfers):

    asset = 'real_asterisk_no_amid'

    def test_given_no_amid_when_create_transfer_from_non_stasis_then_503(self):
        transferred_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis()

        body = {
            'transferred_call': transferred_channel_id,
            'initiator_call': initiator_channel_id,
        }
        body.update(RECIPIENT)
        response = self.ctid_ng.post_transfer_result(body, token=VALID_TOKEN)

        assert_that(response.status_code, equal_to(503))
        assert_that(response.json(), has_entry('message', contains_string('xivo-amid')))
