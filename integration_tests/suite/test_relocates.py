
# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

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
from wazo_calld_client import Client as CalldClient
from wazo_calld_client.exceptions import CalldError

from .helpers.auth import MockUserToken
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import MockUser
from .helpers.confd import MockLine
from .helpers.constants import (
    INVALID_ACL_TOKEN,
    VALID_TOKEN,
)
from .helpers.hamcrest_ import HamcrestARIChannel

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
SOME_CALL_ID = '12345.6789'
SOME_LINE_ID = 12
SOME_LINE_NAME = 'line-name'
SOME_USER_UUID = '68b884c3-515b-4acf-9034-c77896877acb'
SOME_CONTEXT = 'some-context'
STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'integration-tests'

logging.getLogger('swaggerpy.client').setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)


class TestRelocates(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)

    def make_calld(self, token):
        return CalldClient('localhost', self.service_port(9500, 'calld'), token=token, verify_certificate=False)

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

        caller = self.stasis_channel()
        caller_uuid = caller_uuid or str(uuid.uuid4())
        caller.setChannelVar(variable='XIVO_USERUUID', value=caller_uuid)
        bridge.addChannel(channel=caller.id)

        callee = self.stasis_channel()
        callee_uuid = callee_uuid or str(uuid.uuid4())
        callee.setChannelVar(variable='XIVO_USERUUID', value=callee_uuid)
        bridge.addChannel(channel=callee.id)

        calld = self.make_calld(VALID_TOKEN)

        def channels_have_been_created_in_calld(caller_id, callee_id):
            calls = calld.calls.list_calls(application=STASIS_APP, application_instance=STASIS_APP_INSTANCE)
            channel_ids = [call['call_id'] for call in calls['items']]
            return (caller_id in channel_ids and callee_id in channel_ids)

        until.true(channels_have_been_created_in_calld, callee.id, caller.id, tries=3)

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

    def given_mobile_call(self):
        user_uuid = str(uuid.uuid4())
        line_id = SOME_LINE_ID
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id], mobile='mobile-autoanswer'))
        self.confd.set_lines(MockLine(id=line_id, name=SOME_LINE_NAME, protocol='local', context='local'))
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        call = calld.calls.make_call_from_user(extension='dial-autoanswer', from_mobile=True, variables={'CALLEE_XIVO_USERUUID': user_uuid})

        def bridged_channel(caller):
            try:
                bridge = next(bridge for bridge in self.ari.bridges.list()
                              if caller in bridge.json['channels'])
                callee = next(iter(set(bridge.json['channels']) - {caller}))
                return callee
            except StopIteration:
                return False

        callee = until.true(bridged_channel, call['call_id'], timeout=3)

        return call['call_id'], callee, user_uuid

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
        calld = self.make_calld(token)
        destination = 'line'
        location = {'line_id': line_id}
        relocate = calld.relocates.create_from_user(initiator_channel_id, destination, location)

        return relocate, user_uuid, destination, location

    def given_waiting_relocated_user_relocate(self):
        user_uuid = str(uuid.uuid4())
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis(callee_uuid=user_uuid, caller_variables={'WAIT_BEFORE_STASIS': '60'})
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        calld = self.make_calld(token)
        destination = 'line'
        location = {'line_id': line_id}
        relocate = calld.relocates.create_from_user(initiator_channel_id, destination, location)

        def relocate_waiting_relocated():
            assert_that(relocated_channel_id, self.c.is_talking(), 'relocated channel not talking')
            assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
            assert_that(relocate['recipient_call'], self.c.is_talking(), 'recipient channel not talking')

        until.assert_(relocate_waiting_relocated, timeout=5)

        return relocate, user_uuid

    def given_answered_user_relocate(self):
        user_uuid = SOME_USER_UUID
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        calld = self.make_calld(token)
        destination = 'line'
        location = {'line_id': line_id}
        completions = ['api']
        relocate = calld.relocates.create_from_user(initiator_channel_id, destination, location, completions)

        def all_talking():
            assert_that(relocate['relocated_call'], self.c.is_talking(), 'relocated channel not talking')
            assert_that(relocate['initiator_call'], self.c.is_talking(), 'initiator channel not talking')
            assert_that(relocate['recipient_call'], self.c.is_talking(), 'recipient channel not talking')

        until.assert_(all_talking, timeout=5)

        return relocate, user_uuid

    def given_completed_user_relocate(self):
        user_uuid = SOME_USER_UUID
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        calld = self.make_calld(token)
        destination = 'line'
        location = {'line_id': line_id}
        relocate = calld.relocates.create_from_user(initiator_channel_id, destination, location)

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
        super().setUp()
        self.confd.reset()

    def test_given_no_relocates_when_list_then_list_empty(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        result = calld.relocates.list_from_user()

        assert_that(result['items'], empty())

    def test_given_one_relocate_when_list_then_all_fields_are_listed(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        relocate, user_uuid, destination, location = self.given_ringing_user_relocate()
        calld = self.make_calld(token)

        result = calld.relocates.list_from_user()

        assert_that(result['items'], contains({
            'uuid': relocate['uuid'],
            'relocated_call': relocate['relocated_call'],
            'initiator_call': relocate['initiator_call'],
            'recipient_call': relocate['recipient_call'],
            'completions': ['answer'],
            'initiator': user_uuid,
            'timeout': 30,
        }))

    def test_given_one_completed_relocate_when_list_then_relocate_not_found(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)
        relocate, user_uuid = self.given_completed_user_relocate()

        relocates = calld.relocates.list_from_user()

        assert_that(relocates['items'], not_(contains(has_entry('uuid', relocate['uuid']))))

    def test_given_two_relocates_when_list_then_relocates_are_filtered_by_user(self):
        relocate1, user_uuid1, _, __ = self.given_ringing_user_relocate()
        relocate2, user_uuid2, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid2)
        calld = self.make_calld(token)

        result = calld.relocates.list_from_user()

        assert_that(result['items'], contains(has_entries({
            'uuid': relocate2['uuid'],
        })))


class TestGetUserRelocate(TestRelocates):

    def test_given_no_relocate_when_get_then_error_404(self):
        token = self.given_user_token(SOME_USER_UUID)
        calld = self.make_calld(token)

        assert_that(calling(calld.relocates.get_from_user).with_args(relocate_uuid='not-found'),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-relocate',
                    })))

    def test_given_other_relocate_when_get_then_404(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(SOME_USER_UUID)
        calld = self.make_calld(token)

        assert_that(calling(calld.relocates.get_from_user).with_args(relocate['uuid']),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-relocate',
                    })))

    def test_given_relocate_when_get_then_result(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        result = calld.relocates.get_from_user(relocate['uuid'])

        assert_that(result, has_entries({
            'uuid': relocate['uuid'],
        }))


class TestCreateUserRelocate(TestRelocates):

    def setUp(self):
        super().setUp()
        self.confd.reset()

    def test_given_wrong_token_when_relocate_then_401(self):
        calld = self.make_calld(INVALID_ACL_TOKEN)

        assert_that(calling(calld.relocates.create_from_user).with_args(SOME_CALL_ID, 'destination'),
                    raises(CalldError).matching(has_property('status_code', 401)))

    def test_given_invalid_request_when_relocate_then_400(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        assert_that(calling(calld.relocates.create_from_user).with_args(SOME_CALL_ID, 'wrong-destination'),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'invalid-data',
                    })))

    def test_given_token_without_user_when_relocate_then_400(self):
        token = 'some-token'
        self.auth.set_token(MockUserToken(token, user_uuid=None))
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                SOME_CALL_ID,
                'line',
                {'line_id': SOME_LINE_ID}
            ),
            raises(CalldError).matching(has_properties({
                'status_code': 400,
                'error_id': 'token-with-user-uuid-required',
            })))

    def test_given_no_channel_when_relocate_then_403(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                SOME_CALL_ID,
                'line',
                {'line_id': SOME_LINE_ID}
            ),
            raises(CalldError).matching(has_properties({
                'status_code': 403,
                'error_id': 'user-permission-denied',
                'details': has_entries({'user': user_uuid}),
            })))

    def test_given_channel_does_not_belong_to_user_when_relocate_then_403(self):
        user_uuid = SOME_USER_UUID
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis()
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                initiator_channel_id,
                'line',
                {'line_id': SOME_LINE_ID}
            ),
            raises(CalldError).matching(has_properties({
                'status_code': 403,
                'error_id': 'user-permission-denied',
                'details': has_entries({'user': user_uuid}),
            })))

    def test_given_invalid_user_when_relocate_then_400(self):
        user_uuid = SOME_USER_UUID
        line_id = SOME_LINE_ID
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                initiator_channel_id,
                'line',
                {'line_id': line_id}
            ),
            raises(CalldError).matching(has_properties({
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
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                initiator_channel_id,
                'line',
                {'line_id': line_id}
            ),
            raises(CalldError).matching(has_properties({
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
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                initiator_channel.id,
                'line',
                {'line_id': line_id}
            ),
            raises(CalldError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-creation-error',
            })))

    def test_given_relocate_started_when_relocate_again_then_409(self):
        relocate, user_uuid, destination, location = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                relocate['initiator_call'],
                destination,
                location,
            ),
            raises(CalldError).matching(has_properties({
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
        events = self.bus.accumulator('calls.relocate.*')
        calld = self.make_calld(token)

        relocate = calld.relocates.create_from_user(initiator_channel_id, 'line', {'line_id': line_id})

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocated_channel_id,
            initiator_channel_id,
            relocate['recipient_call'],
            timeout=5,
        )

        def relocate_events_received():
            assert_that(events.accumulate(), contains(
                has_entries({
                    'name': 'relocate_initiated',
                    'data': relocate,
                }),
                has_entries({
                    'name': 'relocate_answered',
                    'data': relocate,
                }),
                has_entries({
                    'name': 'relocate_completed',
                    'data': relocate,
                }),
                has_entries({
                    'name': 'relocate_ended',
                    'data': relocate,
                }),
            ))

        until.assert_(relocate_events_received)

    def test_given_non_stasis_channels_a_b_when_b_relocate_to_c_and_answer_then_a_c(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_not_stasis(callee_uuid=user_uuid)
        events = self.bus.accumulator('calls.relocate.*')
        calld = self.make_calld(token)

        relocate = calld.relocates.create_from_user(initiator_channel_id, 'line', {'line_id': line_id})

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocated_channel_id,
            initiator_channel_id,
            relocate['recipient_call'],
            timeout=5,
        )

        def relocate_events_received():
            assert_that(events.accumulate(), contains(
                has_entries({
                    'name': 'relocate_initiated',
                    'data': relocate,
                }),
                has_entries({
                    'name': 'relocate_answered',
                    'data': relocate,
                }),
                has_entries({
                    'name': 'relocate_completed',
                    'data': relocate,
                }),
                has_entries({
                    'name': 'relocate_ended',
                    'data': relocate,
                }),
            ))

        until.assert_(relocate_events_received)

    def test_given_b_has_no_mobile_when_b_relocate_to_mobile_then_400(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id], mobile=None))
        self.confd.set_lines(MockLine(id=line_id, context='local'))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.create_from_user).with_args(
                initiator_channel_id,
                'mobile',
            ),
            raises(CalldError).matching(has_properties({
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
        calld = self.make_calld(token)

        relocate = calld.relocates.create_from_user(initiator_channel_id, 'mobile')

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

    def test_given_relocate_ringing_when_api_cancel_then_relocate_cancelled(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        calld.relocates.cancel_from_user(relocate['uuid'])

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

    def test_given_relocate_waiting_relocated_when_api_cancel_then_400(self):
        relocate, user_uuid = self.given_waiting_relocated_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.cancel_from_user).with_args(
                relocate['uuid'],
            ),
            raises(CalldError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-cancellation-error',
            })))

    def test_given_relocate_completion_api_when_api_complete_then_relocate_completed(self):
        relocate, user_uuid = self.given_answered_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        calld.relocates.complete_from_user(relocate['uuid'])

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocate['relocated_call'],
            relocate['initiator_call'],
            relocate['recipient_call'],
            timeout=5,
        )

    def test_given_relocate_waiting_completion_when_api_cancel_then_relocate_cancelled(self):
        relocate, user_uuid = self.given_answered_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        calld.relocates.cancel_from_user(relocate['uuid'])

        def relocate_cancelled():
            assert_that(relocate['relocated_call'], self.c.is_talking(), 'relocated not talking')
            assert_that(relocate['initiator_call'], self.c.is_talking(), 'initiator not talking')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(relocate_cancelled, timeout=3)

    def test_given_relocate_waiting_completion_when_initiator_hangs_up_then_all_hangup(self):
        relocate, user_uuid = self.given_answered_user_relocate()

        self.ari.channels.hangup(channelId=relocate['initiator_call'])

        def all_hungup():
            assert_that(relocate['relocated_call'], self.c.is_hungup(), 'relocated not hungup')
            assert_that(relocate['initiator_call'], self.c.is_hungup(), 'initiator not hungup')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(all_hungup, timeout=3)

    def test_given_relocate_waiting_completion_when_relocated_hangs_up_then_all_hangup(self):
        relocate, user_uuid = self.given_answered_user_relocate()

        self.ari.channels.hangup(channelId=relocate['relocated_call'])

        def all_hungup():
            assert_that(relocate['relocated_call'], self.c.is_hungup(), 'relocated not hungup')
            assert_that(relocate['initiator_call'], self.c.is_hungup(), 'initiator not hungup')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(all_hungup, timeout=3)

    def test_given_relocate_waiting_completion_when_recipient_hangs_up_then_cancelled(self):
        relocate, user_uuid = self.given_answered_user_relocate()

        self.ari.channels.hangup(channelId=relocate['recipient_call'])

        def relocate_cancelled():
            assert_that(relocate['relocated_call'], self.c.is_talking(), 'relocated not talking')
            assert_that(relocate['initiator_call'], self.c.is_talking(), 'initiator not talking')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')

        until.assert_(relocate_cancelled, timeout=3)

    def test_given_ringing_relocate_when_api_complete_then_400(self):
        relocate, user_uuid, _, __ = self.given_ringing_user_relocate()
        token = self.given_user_token(user_uuid)
        calld = self.make_calld(token)

        assert_that(
            calling(calld.relocates.complete_from_user).with_args(
                relocate['uuid'],
            ),
            raises(CalldError).matching(has_properties({
                'status_code': 400,
                'error_id': 'relocate-completion-error',
            })))

    def test_given_mobile_call_when_relocate_to_line_then_relocate_completed(self):
        mobile_channel, other_channel, mobile_user_uuid = self.given_mobile_call()
        token = self.given_user_token(mobile_user_uuid)
        line_id = SOME_LINE_ID
        calld = self.make_calld(token)
        self.confd.set_users(MockUser(uuid=mobile_user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        destination = 'line'
        location = {'line_id': line_id}

        relocate = calld.relocates.create_from_user(mobile_channel, destination, location)

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocate['relocated_call'],
            relocate['initiator_call'],
            relocate['recipient_call'],
            timeout=5,
        )

    def test_given_call_when_relocate_to_mobile_and_relocate_to_line_then_relocate_completed(self):
        user_uuid = SOME_USER_UUID
        initiator_channel, callee_channel = self.given_bridged_call_stasis(caller_uuid=user_uuid)
        token = self.given_user_token(user_uuid)
        line_id = SOME_LINE_ID
        calld = self.make_calld(token)
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id], mobile='recipient_autoanswer'))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context='local'))

        relocate = calld.relocates.create_from_user(initiator_channel, destination='mobile')

        def relocate_finished(relocate):
            assert_that(calling(calld.relocates.get_from_user).with_args(relocate['uuid']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 404,
                            'error_id': 'no-such-relocate',
                        })))

        until.assert_(
            relocate_finished,
            relocate,
            timeout=5,
        )

        initiator_channel = relocate['recipient_call']
        destination = 'line'
        location = {'line_id': line_id}

        relocate = calld.relocates.create_from_user(initiator_channel, destination, location)

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocate['relocated_call'],
            relocate['initiator_call'],
            relocate['recipient_call'],
            timeout=5,
        )

    def test_given_timeout_when_relocate_noanswer_then_relocate_cancelled(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='ring@local', protocol='local', context=SOME_CONTEXT))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        calld = self.make_calld(token)

        relocate = calld.relocates.create_from_user(initiator_channel_id, 'line', {'line_id': line_id}, timeout=1)

        def relocate_cancelled():
            assert_that(relocate['relocated_call'], self.c.is_talking(), 'relocated not talking')
            assert_that(relocate['initiator_call'], self.c.is_talking(), 'initiator not talking')
            assert_that(relocate['recipient_call'], self.c.is_hungup(), 'recipient not hungup')
            assert_that(calling(calld.relocates.get_from_user).with_args(relocate['uuid']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 404,
                            'error_id': 'no-such-relocate',
                        })))

        until.assert_(relocate_cancelled, timeout=3)
