# -*- coding: utf-8 -*-

# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from ari.exceptions import ARINotInStasis
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import has_entry
from xivo_test_helpers import until
from xivo_ctid_ng_client import Client as CtidNGClient

from .test_api.base import RealAsteriskIntegrationTest
from .test_api.confd import MockUser
from .test_api.confd import MockLine
from .test_api.auth import MockUserToken
from .test_api.hamcrest_ import HamcrestARIChannel

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
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

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))

        return token

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
                              )))
        assert_that(relocated_channel_id, self.c.is_talking(), 'relocated channel not talking')
        assert_that(initiator_channel_id, self.c.is_hungup(), 'initiator channel is still talking')
        assert_that(recipient_channel_id, self.c.is_talking(), 'recipient channel not talking')


class TestCreateUserRelocate(TestRelocates):

    def setUp(self):
        super(TestCreateUserRelocate, self).setUp()
        self.confd.reset()

    def test_given_stasis_channels_a_b_when_b_relocate_to_c_and_answer_then_a_c(self):
        user_uuid = SOME_USER_UUID
        line_id = 12
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[line_id]))
        self.confd.set_lines(MockLine(id=line_id, name='recipient_autoanswer@local', protocol='local', context=SOME_CONTEXT))
        token = self.given_user_token(user_uuid)
        relocated_channel_id, initiator_channel_id = self.given_bridged_call_stasis(callee_uuid=user_uuid)
        ctid_ng = self.make_ctid_ng(token)

        relocate = ctid_ng.relocates.create_from_user(initiator_channel_id, line_id)

        until.assert_(
            self.assert_relocate_is_completed,
            relocate['uuid'],
            relocated_channel_id,
            initiator_channel_id,
            relocate['recipient_call'],
            tries=5
        )
