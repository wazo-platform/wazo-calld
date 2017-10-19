# -*- coding: utf-8 -*-

# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from ari.exceptions import ARINotInStasis
from hamcrest import assert_that
from hamcrest import calling
from hamcrest import contains
from hamcrest import contains_inanyorder
from hamcrest import empty
from hamcrest import has_entry
from hamcrest import has_entries
from hamcrest import has_properties
from hamcrest import has_property
from hamcrest import not_
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from xivo_ctid_ng_client import Client as CtidNGClient
from xivo_ctid_ng_client.exceptions import CtidNGError

from .test_api.auth import MockUserToken
from .test_api.base import RealAsteriskIntegrationTest
from .test_api.confd import MockUser
from .test_api.confd import MockLine
from .test_api.constants import INVALID_ACL_TOKEN
from .test_api.hamcrest_ import HamcrestARIChannel

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
SOME_CALL_ID = '12345.6789'
SOME_LINE_ID = 12
SOME_USER_UUID = '68b884c3-515b-4acf-9034-c77896877acb'
SOME_CONTEXT = 'some-context'
STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'integration-tests'

logging.getLogger('swaggerpy.client').setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)


class TestRelocates(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super(TestRelocates, self).setUp()
        self.c = HamcrestARIChannel(self.ari)

    def make_ctid_ng(self, token):
        return CtidNGClient('localhost', self.service_port(9500, 'ctid-ng'), token=token, verify_certificate=False)

    def stasis_channel(self):
        def channel_is_in_stasis(channel_id):
            try:
                self.ari.channels.setChannelVar(channelId=channel_id, variable='TEST_STASIS', value='')
                return True
            except ARINotInStasis:
                return False

        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=STASIS_APP,
                                                  appArgs=[STASIS_APP_INSTANCE])
        until.true(channel_is_in_stasis, new_channel.id, tries=2)

        return new_channel

    def given_bridged_call_stasis(self, caller_uuid=None, callee_uuid=None):
        bridge = self.ari.bridges.create(type='mixing')
        bus_events = self.bus.accumulator('calls.call.created')

        caller = self.stasis_channel()
        caller_uuid = caller_uuid or str(uuid.uuid4())
        caller.setChannelVar(variable='XIVO_USERUUID', value=caller_uuid)
        bridge.addChannel(channel=caller.id)

        callee = self.stasis_channel()
        callee_uuid = callee_uuid or str(uuid.uuid4())
        callee.setChannelVar(variable='XIVO_USERUUID', value=callee_uuid)
        bridge.addChannel(channel=callee.id)

        def channels_have_been_created_in_ctid_ng(caller_id, callee_id):
            created_channel_ids = [message['data']['call_id'] for message in bus_events.accumulate()]
            return (caller_id in created_channel_ids and
                    callee_id in created_channel_ids)

        until.true(channels_have_been_created_in_ctid_ng, callee.id, caller.id, tries=3)

        return caller.id, callee.id

    def given_bridged_call_not_stasis(self, caller_uuid=None, callee_uuid=None, caller_variables=None):
        caller_uuid = caller_uuid or str(uuid.uuid4())
        callee_uuid = callee_uuid or str(uuid.uuid4())
        variables = {'XIVO_USERUUID': caller_uuid,
                     '__CALLEE_XIVO_USERUUID': callee_uuid}
        variables.update(caller_variables or {})
        caller = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                             context='local',
                                             extension='dial-autoanswer',
                                             variables={'variables': variables})

        def bridged_channel(caller):
            try:
                bridge = next(bridge for bridge in self.ari.bridges.list()
                              if caller.id in bridge.json['channels'])
                callee_channel_id = next(iter(set(bridge.json['channels']) - {caller.id}))
                return callee_channel_id
            except StopIteration:
                return False

        callee_channel_id = until.true(bridged_channel, caller, timeout=3)
        return caller.id, callee_channel_id

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))

        return token

    def given_ringing_user_relocate(self):
        user_uuid = str(uuid.uuid4())
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient@local', protocol='local', context=SOME_CONTEXT))
        ctid_ng = self.make_ctid_ng(token)
        destination = 'line'
        location = {'line_id': line_id}
        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, destination, location)

        return relocate, user_uuid, destination, location

    def given_waiting_relocated_user_relocate(self):
        user_uuid = str(uuid.uuid4())
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis(callee_uuid=user_uuid, caller_variables={'WAIT_BEFORE_STASIS': '60'})
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        ctid_ng = self.make_ctid_ng(token)
        destination = 'line'
        location = {'line_id': line_id}
        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, destination, location)

        def relocate_waiting_relocated():
            assert_that(relocated_channel_id, self.c.is_talking(), 'relocated channel not talking')
            assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
            assert_that(relocate['recipient_call'], self.c.is_talking(), 'recipient channel not talking')

        until.assert_(relocate_waiting_relocated, timeout=5)

        return relocate, user_uuid

    def given_completed_user_relocate(self):
        user_uuid = SOME_USER_UUID
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        ctid_ng = self.make_ctid_ng(token)
        destination = 'line'
        location = {'line_id': line_id}
        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, destination, location)

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocate['relocated_call'],
            relocate['initiator_call'],
            relocate['recipient_call'],
            timeout=5,
        )

        return relocate, user_uuid

    def assert_relocate_is_completed(self, relocate_uuid, relocated_channel_id, initiator_channel_id, recipient_channel_id):
        try:
            relocate_bridge = next(bridge for bridge in self.ari.bridges.list() if bridge.json['name'] == 'relocate:{}'.format(relocate_uuid))
        except StopIteration:
            raise AssertionError('relocate bridge not found')

        assert_that(relocate_bridge.json,
                    has_entry('channels',
                              contains_inanyorder(
                                  relocated_channel_id,
                                  recipient_channel_id
                              )),
                    'relocate is missing a channel')
        assert_that(relocated_channel_id, self.c.is_talking(), 'relocated channel not talking')
        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
        assert_that(recipient_channel_id, self.c.is_talking(), 'recipient channel not talking')


class TestListUserRelocate(TestRelocates):

    def setUp(self):
        super(TestListUserRelocate, self).setUp()
        self.confd.reset()

    def test_given_no_relocates_when_list_then_list_empty(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        result = ctid_ng.relocates.list_from_user()

        assert_that(result['items'], empty())

    def test_given_one_relocate_when_list_then_all_fields_are_listed(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        relocate, user_uuid, destination, location = self.given_ringing_user_relocate()
        ctid_ng = self.make_ctid_ng(token)

        result = ctid_ng.relocates.list_from_user()

        assert_that(result['items'], contains({
            'uuid': relocate['uuid'],
            'relocated_call': relocate['relocated_call'],
            'initiator_call': relocate['initiator_call'],
            'recipient_call': relocate['recipient_call'],
            'completions': 'answer',
        }))

    def test_given_one_completed_relocate_when_list_then_relocate_not_found(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        ctid_ng = self.make_ctid_ng(token)
        relocate, user_uuid = self.given_completed_user_relocate()

        relocates = ctid_ng.relocates.list_from_user()

        assert_that(relocates['items'], not_(contains(has_entry('uuid', relocate['uuid']))))

    def test_given_two_relocates_when_list_then_relocates_are_filtered_by_user(self):
        relocate1, user_uuid1, _, __ = self.given_ringing_user_relocate()
        relocate2, user_uuid2, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid2)
        ctid_ng = self.make_ctid_ng(token)

        result = ctid_ng.relocates.list_from_user()

        assert_that(result['items'], contains(has_entries({
            'uuid': relocate2['uuid'],
        })))


class TestGetUserRelocate(TestRelocates):

    def test_given_no_relocate_when_get_then_error_404(self):
        token = self.given_user_token(SOME_USER_UUID)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(calling(ctid_ng.relocates.get_from_user).with_args(relocate_uuid='not-found'),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-relocate',
                    })))

    def test_given_other_relocate_when_get_then_404(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(SOME_USER_UUID)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(calling(ctid_ng.relocates.get_from_user).with_args(relocate['uuid']),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-relocate',
                    })))

    def test_given_relocate_when_get_then_result(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        result = ctid_ng.relocates.get_from_user(relocate['uuid'])

        assert_that(result, has_entries({
            'uuid': relocate['uuid'],
        }))


class TestCreateUserRelocate(TestRelocates):

    def setUp(self):
        super(TestCreateUserRelocate, self).setUp()
        self.confd.reset()

    def test_given_wrong_token_when_relocate_then_401(self):
        ctid_ng = self.make_ctid_ng(INVALID_ACL_TOKEN)

        assert_that(calling(ctid_ng.relocates.create_from_user).with_args(SOME_CALL_ID, 'destination'),
                    raises(CtidNGError).matching(has_property('status_code', 401)))

    def test_given_invalid_request_when_relocate_then_400(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(calling(ctid_ng.relocates.create_from_user).with_args(SOME_CALL_ID, 'wrong-destination'),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'invalid-data',
                    })))

    def test_given_token_without_user_when_relocate_then_400(self):
        token = 'some-token'
        self.auth.set_token(MockUserToken(token, user_uuid=None))
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                SOME_CALL_ID,
                'line',
                {'line_id': SOME_LINE_ID}
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'token-with-user-uuid-required',
            })))

    def test_given_no_channel_when_relocate_then_403(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                SOME_CALL_ID,
                'line',
                {'line_id': SOME_LINE_ID}
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 403,
                'error_id': 'user-permission-denied',
                'details': has_entries({'user': user_uuid}),
            })))

    def test_given_channel_does_not_belong_to_user_when_relocate_then_403(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                initiator_channel_id,
                'line',
                {'line_id': SOME_LINE_ID}
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 403,
                'error_id': 'user-permission-denied',
                'details': has_entries({'user': user_uuid}),
            })))

    def test_given_invalid_user_when_relocate_then_400(self):
        user_uuid = SOME_USER_UUID
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                initiator_channel_id,
                'line',
                {'line_id': line_id}
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-creation-error',
                'details': has_entries({'user_uuid': user_uuid}),
            })))

    def test_given_invalid_line_when_relocate_then_400(self):
        user_uuid = SOME_USER_UUID
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid))
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                initiator_channel_id,
                'line',
                {'line_id': line_id}
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-creation-error',
                'details': has_entries({'line_id': line_id}),
            })))

    def test_given_only_one_channel_when_relocate_then_400(self):
        user_uuid = SOME_USER_UUID
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        initiator_channel = self.stasis_channel()
        initiator_channel.setChannelVar(variable='XIVO_USERUUID', value=user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                initiator_channel.id,
                'line',
                {'line_id': line_id}
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-creation-error',
            })))

    def test_given_relocate_started_when_relocate_again_then_409(self):
        relocate, user_uuid, destination, location = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                relocate['initiator_call'],
                destination,
                location,
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 409,
                'error_id': 'relocate-already-started',
            })))

    def test_given_stasis_channels_a_b_when_b_relocate_to_c_and_answer_then_a_c(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, 'line', {'line_id': line_id})

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocated_channel_id,
            initiator_channel_id,
            relocate['recipient_call'],
            timeout=5,
        )

    def test_given_non_stasis_channels_a_b_when_b_relocate_to_c_and_answer_then_a_c(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis(callee_uuid=user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, 'line', {'line_id': line_id})

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocated_channel_id,
            initiator_channel_id,
            relocate['recipient_call'],
            timeout=5,
        )

    def test_given_b_has_no_mobile_when_b_relocate_to_mobile_then_400(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id], mobile=None))
        self.confd.set_lines(MockLine(id=line_id, context='local'))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        assert_that(
            calling(ctid_ng.relocates.create_from_user).with_args(
                initiator_channel_id,
                'mobile',
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-creation-error',
            })))

    def test_given_stasis_channels_a_b_when_b_relocate_to_mobile_and_answer_then_a_talks_with_mobile(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id], mobile='recipient_autoanswer'))
        self.confd.set_lines(MockLine(id=line_id, context='local'))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, 'mobile')

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocated_channel_id,
            initiator_channel_id,
            relocate['recipient_call'],
            timeout=5,
        )

    def test_given_relocate_ringing_when_relocated_hangs_up_then_all_hangup(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()

        self.ari.channels.hangup(channelId=relocate['relocated_call'])

        def all_hungup():
            assert_that(relocate['relocated_call'], self.c.is_hungup(), 'relocated not hungup')
            assert_that(relocate['initiator_call'], self.c.is_hungup(), 'initiator not hungup')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(all_hungup, timeout=3)

    def test_given_relocate_ringing_when_initiator_hangs_up_then_all_hangup(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()

        self.ari.channels.hangup(channelId=relocate['initiator_call'])

        def all_hungup():
            assert_that(relocate['relocated_call'], self.c.is_hungup(), 'relocated not hungup')
            assert_that(relocate['initiator_call'], self.c.is_hungup(), 'initiator not hungup')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(all_hungup, timeout=3)

    def test_given_relocate_ringing_when_recipient_hangs_up_then_relocate_cancelled(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()

        self.ari.channels.hangup(channelId=relocate['recipient_call'])

        def relocate_cancelled():
            assert_that(relocate['relocated_call'], self.c.is_talking(), 'relocated not talking')
            assert_that(relocate['initiator_call'], self.c.is_talking(), 'initiator not talking')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(relocate_cancelled, timeout=3)

    def test_given_relocate_waiting_relocated_when_relocated_hangs_up_then_all_hangup(self):
        relocate, user_uuid = self.given_waiting_relocated_user_relocate()

        self.ari.channels.hangup(channelId=relocate['relocated_call'])

        def all_hungup():
            assert_that(relocate['relocated_call'], self.c.is_hungup(), 'relocated not hungup')
            assert_that(relocate['initiator_call'], self.c.is_hungup(), 'initiator not hungup')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(all_hungup, timeout=3)

    def test_given_relocate_waiting_relocated_when_recipient_hangs_up_then_all_hangup(self):
        relocate, user_uuid = self.given_waiting_relocated_user_relocate()

        self.ari.channels.hangup(channelId=relocate['recipient_call'])

        def all_hungup():
            assert_that(relocate['relocated_call'], self.c.is_hungup(), 'relocated not hungup')
            assert_that(relocate['initiator_call'], self.c.is_hungup(), 'initiator not hungup')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(all_hungup, timeout=3)
