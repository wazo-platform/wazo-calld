# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import uuid
from typing import Any

import pytest
from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    contains_inanyorder,
    contains_string,
    empty,
    equal_to,
    has_entries,
    has_item,
    has_items,
    has_properties,
    not_,
    starts_with,
)
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers import until
from wazo_test_helpers.auth import MockUserToken
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.ari_ import MockApplication, MockBridge, MockChannel
from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id, new_uuid
from .helpers.confd import MockLine, MockUser
from .helpers.constants import (
    CALLD_SERVICE_TENANT,
    ENDPOINT_AUTOANSWER,
    SOME_LINE_ID,
    VALID_TENANT,
    VALID_TOKEN,
)
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsterisk, RealAsteriskIntegrationTest
from .helpers.wait_strategy import CalldUpWaitStrategy

SOME_LOCAL_CHANNEL_NAME = 'Local/channel'
SOME_PRIORITY = 1
UNKNOWN_UUID = '00000000-0000-0000-0000-000000000000'

CONFD_SIP_PROTOCOL = 'sip'


class _BaseTestCalls(IntegrationTest):
    def _set_channel_variable(self, variables):
        for _, values in variables.items():
            values.setdefault('WAZO_TENANT_UUID', VALID_TENANT)
        self.ari.set_channel_variable(variables)


class TestListCalls(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_list_calls_then_empty_list(self):
        calls = self.calld_client.calls.list_calls()

        assert_that(calls, has_entries(items=contains_exactly()))

    def test_given_some_calls_with_user_id_when_list_calls_then_calls_are_complete(
        self,
    ):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(
            MockChannel(
                id=first_id,
                caller_id_name='Weber',
                caller_id_number='4185556666',
                connected_line_name='Denis',
                connected_line_number='4185557777',
                creation_time='first-time',
                state='Up',
                channelvars={'CHANNEL(videonativeformat)': '(vp8|vp9)'},
            ),
            MockChannel(
                id=second_id,
                caller_id_name='Denis',
                caller_id_number='4185557777',
                connected_line_name='Weber',
                connected_line_number='4185556666',
                creation_time='second-time',
                state='Ringing',
                channelvars={'CHANNEL(videonativeformat)': '(nothing)'},
            ),
        )
        self._set_channel_variable(
            {
                first_id: {
                    'WAZO_USERUUID': 'user1-uuid',
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                    'CHANNEL(channeltype)': 'other',
                    'WAZO_LINE_ID': str(SOME_LINE_ID),
                    'CHANNEL(linkedid)': 'first-conversation-id',
                },
                second_id: {
                    'WAZO_USERUUID': 'user2-uuid',
                    'WAZO_CHANNEL_DIRECTION': 'from-wazo',
                    'CHANNEL(channeltype)': 'PJSIP',
                    'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
                    'WAZO_LINE_ID': '1235',
                    'CHANNEL(linkedid)': 'first-conversation-id',
                },
            }
        )
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=[first_id, second_id]))
        self.confd.set_users(MockUser(uuid='user1-uuid'), MockUser(uuid='user2-uuid'))

        calls = self.calld_client.calls.list_calls()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(
                        call_id=first_id,
                        conversation_id='first-conversation-id',
                        user_uuid='user1-uuid',
                        status='Up',
                        bridges=['bridge-id'],
                        talking_to={second_id: 'user2-uuid'},
                        creation_time='first-time',
                        caller_id_number='4185556666',
                        caller_id_name='Weber',
                        peer_caller_id_number='4185557777',
                        peer_caller_id_name='Denis',
                        sip_call_id=None,
                        line_id=SOME_LINE_ID,
                        is_caller=True,
                        is_video=True,
                    ),
                    has_entries(
                        call_id=second_id,
                        conversation_id='first-conversation-id',
                        user_uuid='user2-uuid',
                        status='Ringing',
                        bridges=['bridge-id'],
                        talking_to={first_id: 'user1-uuid'},
                        creation_time='second-time',
                        caller_id_number='4185557777',
                        caller_id_name='Denis',
                        peer_caller_id_number='4185556666',
                        peer_caller_id_name='Weber',
                        sip_call_id='a-sip-call-id',
                        line_id=1235,
                        is_caller=False,
                        is_video=False,
                    ),
                )
            ),
        )

    def test_call_direction(self):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable(
            {
                first_id: {'WAZO_CALL_DIRECTION': 'internal'},
                second_id: {'WAZO_CALL_DIRECTION': 'outbound'},
            }
        )
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=[first_id, second_id]))

        calls = self.calld_client.calls.list_calls()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id, direction='outbound'),
                    has_entries(call_id=second_id, direction='outbound'),
                )
            ),
        )

    def test_given_some_calls_and_no_user_id_when_list_calls_then_list_calls_with_no_user_uuid(
        self,
    ):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable({first_id: {}, second_id: {}})

        calls = self.calld_client.calls.list_calls()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id, user_uuid=None),
                    has_entries(call_id=second_id, user_uuid=None),
                )
            ),
        )

    def test_given_some_calls_when_list_calls_by_application_then_list_of_calls_is_filtered(
        self,
    ):
        first_id, second_id, third_id = (
            new_call_id(),
            new_call_id(leap=1),
            new_call_id(leap=2),
        )
        self.ari.set_channels(
            MockChannel(id=first_id),
            MockChannel(id=second_id),
            MockChannel(id=third_id),
        )
        self._set_channel_variable({first_id: {}, second_id: {}, third_id: {}})
        self.ari.set_applications(
            MockApplication(name='my-app', channels=[first_id, third_id])
        )

        calls = self.calld_client.calls.list_calls(application='my-app')

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id),
                    has_entries(call_id=third_id),
                )
            ),
        )

    def test_given_some_calls_and_no_applications_when_list_calls_by_application_then_no_calls(
        self,
    ):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable({first_id: {}, second_id: {}})

        calls = self.calld_client.calls.list_calls(application='my-app')

        assert_that(calls, has_entries(items=empty()))

    def test_given_some_calls_when_list_calls_by_application_instance_then_list_of_calls_is_filtered(
        self,
    ):
        first_id, second_id, third_id, fourth_id = (
            new_call_id(),
            new_call_id(leap=1),
            new_call_id(leap=2),
            new_call_id(leap=3),
        )
        self.ari.set_channels(
            MockChannel(id=first_id),
            MockChannel(id=second_id),
            MockChannel(id=third_id),
            MockChannel(id=fourth_id),
        )
        self._set_channel_variable(
            {first_id: {}, second_id: {}, third_id: {}, fourth_id: {}}
        )
        self.ari.set_applications(
            MockApplication(name='my-app', channels=[first_id, second_id, third_id])
        )
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{first_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appX', 'state': 'talking'}
                ),
                f'XIVO_CHANNELS_{second_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appY', 'state': 'talking'}
                ),
                f'XIVO_CHANNELS_{third_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appX', 'state': 'talking'}
                ),
            }
        )

        calls = self.calld_client.calls.list_calls(
            application='my-app',
            application_instance='appX',
        )

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id),
                    has_entries(call_id=third_id),
                )
            ),
        )

    def test_given_some_calls_and_application_bound_to_all_channels_when_list_calls_by_application_then_all_calls(
        self,
    ):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable({first_id: {}, second_id: {}})
        self.ari.set_applications(
            MockApplication(name='my-app', channels=['__AST_CHANNEL_ALL_TOPIC'])
        )

        calls = self.calld_client.calls.list_calls(application='my-app')

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id),
                    has_entries(call_id=second_id),
                )
            ),
        )

    def test_given_some_calls_and_application_bound_to_all_channels_when_list_calls_by_application_instance_then_calls_are_still_filtered_by_application(
        self,
    ):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable({first_id: {}, second_id: {}})
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{first_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appX', 'state': 'talking'}
                ),
                f'XIVO_CHANNELS_{second_id}': json.dumps(
                    {'app': 'another-app', 'app_instance': 'appX', 'state': 'talking'}
                ),
            }
        )
        self.ari.set_applications(
            MockApplication(name='my-app', channels=['__AST_CHANNEL_ALL_TOPIC'])
        )

        calls = self.calld_client.calls.list_calls(
            application='my-app',
            application_instance='appX',
        )

        assert_that(
            calls,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=first_id),
                )
            ),
        )

    def test_given_local_channels_when_list_then_talking_to_is_none(self):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(
            MockChannel(id=first_id),
            MockChannel(id=second_id, name=SOME_LOCAL_CHANNEL_NAME),
        )
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=[first_id, second_id]))
        self.confd.set_users(MockUser(uuid='user1-uuid'), MockUser(uuid='user2-uuid'))
        self._set_channel_variable(
            {
                first_id: {'WAZO_USERUUID': 'user1-uuid'},
                second_id: {'WAZO_USERUUID': 'user2-uuid'},
            }
        )

        calls = self.calld_client.calls.list_calls()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id, talking_to={second_id: None}),
                    has_entries(call_id=second_id, talking_to={first_id: 'user1-uuid'}),
                )
            ),
        )

    def test_list_calls_tenant_isolation(
        self,
    ):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        tenant_uuid_1 = str(uuid.uuid4())
        tenant_uuid_2 = str(uuid.uuid4())
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable(
            {
                first_id: {'WAZO_TENANT_UUID': tenant_uuid_1},
                second_id: {'WAZO_TENANT_UUID': tenant_uuid_2},
            }
        )
        calld_1 = self.make_user_calld(user_uuid_1, tenant_uuid=tenant_uuid_1)
        calld_2 = self.make_user_calld(user_uuid_2, tenant_uuid=tenant_uuid_2)

        calls_1 = calld_1.calls.list_calls()
        calls_2 = calld_2.calls.list_calls()

        assert_that(
            calls_1,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=first_id),
                )
            ),
        )
        assert_that(
            calls_2,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=second_id),
                )
            ),
        )

    def test_list_calls_recurse(
        self,
    ):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        top_tenant_uuid = CALLD_SERVICE_TENANT
        subtenant_uuid = VALID_TENANT
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable(
            {
                first_id: {'WAZO_TENANT_UUID': top_tenant_uuid},
                second_id: {'WAZO_TENANT_UUID': subtenant_uuid},
            }
        )
        calld_top_tenant = self.make_user_calld(
            user_uuid_1, tenant_uuid=top_tenant_uuid
        )
        calld_subtenant = self.make_user_calld(user_uuid_2, tenant_uuid=subtenant_uuid)

        # top tenant without recurse
        calls = calld_top_tenant.calls.list_calls(recurse=False)
        assert_that(
            calls,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=first_id),
                )
            ),
        )

        # top tenant with recurse
        calls = calld_top_tenant.calls.list_calls(recurse=True)
        assert_that(
            calls,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=first_id),
                    has_entries(call_id=second_id),
                )
            ),
        )

        # sub tenant without recurse
        calls = calld_subtenant.calls.list_calls(recurse=False)
        assert_that(
            calls,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=second_id),
                )
            ),
        )

        # sub tenant with recurse
        calls = calld_subtenant.calls.list_calls(recurse=True)
        assert_that(
            calls,
            has_entries(
                items=contains_exactly(
                    has_entries(call_id=second_id),
                )
            ),
        )


class TestUserListCalls(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_list_calls_then_empty_list(self):
        user_uuid = 'user-uuid'
        calld_client = self.make_user_calld(user_uuid)
        calls = calld_client.calls.list_calls_from_user()

        assert_that(calls, has_entries(items=contains_exactly()))

    def test_given_some_calls_with_user_id_when_list_my_calls_then_calls_are_filtered_by_user(
        self,
    ):
        user_uuid = 'user-uuid'
        my_call_id = new_call_id()
        my_second_call_id = new_call_id(leap=1)
        others_call_id = new_call_id(leap=2)
        no_user_call_id = new_call_id(leap=3)
        self.ari.set_channels(
            MockChannel(id=my_call_id, channelvars={'WAZO_USERUUID': user_uuid}),
            MockChannel(id=my_second_call_id, channelvars={'WAZO_USERUUID': user_uuid}),
            MockChannel(id=others_call_id, channelvars={'WAZO_USERUUID': 'user2-uuid'}),
            MockChannel(id=no_user_call_id),
        )
        self._set_channel_variable(
            {
                my_call_id: {'WAZO_USERUUID': user_uuid},
                my_second_call_id: {'WAZO_USERUUID': user_uuid},
                others_call_id: {'WAZO_USERUUID': 'user2-uuid'},
            }
        )
        self.confd.set_users(MockUser(uuid=user_uuid), MockUser(uuid='user2-uuid'))
        calld_client = self.make_user_calld(user_uuid)

        calls = calld_client.calls.list_calls_from_user()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=my_call_id, user_uuid=user_uuid),
                    has_entries(call_id=my_second_call_id, user_uuid=user_uuid),
                )
            ),
        )

    def test_given_some_calls_when_list_calls_by_application_then_list_of_calls_is_filtered(
        self,
    ):
        first_id, second_id, third_id = (
            new_call_id(),
            new_call_id(leap=1),
            new_call_id(leap=2),
        )
        user_uuid = 'user-uuid'
        self.ari.set_channels(
            MockChannel(id=first_id),
            MockChannel(id=second_id),
            MockChannel(id=third_id),
        )
        self.ari.set_applications(
            MockApplication(name='my-app', channels=[first_id, third_id])
        )
        self._set_channel_variable(
            {
                first_id: {'WAZO_USERUUID': user_uuid},
                second_id: {'WAZO_USERUUID': user_uuid},
                third_id: {'WAZO_USERUUID': user_uuid},
            }
        )
        calld_client = self.make_user_calld(user_uuid)

        calls = calld_client.calls.list_calls_from_user(application='my-app')

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id),
                    has_entries(call_id=third_id),
                )
            ),
        )

    def test_given_some_calls_and_no_applications_when_list_calls_by_application_then_no_calls(
        self,
    ):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        user_uuid = 'user-uuid'
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable(
            {
                first_id: {'WAZO_USERUUID': user_uuid},
                second_id: {'WAZO_USERUUID': user_uuid},
            }
        )
        calld_client = self.make_user_calld(user_uuid)

        calls = calld_client.calls.list_calls_from_user(application='my-app')

        assert_that(calls, has_entries(items=empty()))

    def test_given_some_calls_when_list_calls_by_application_instance_then_list_of_calls_is_filtered(
        self,
    ):
        first_id, second_id, third_id, fourth_id = (
            new_call_id(),
            new_call_id(leap=1),
            new_call_id(leap=2),
            new_call_id(leap=3),
        )
        user_uuid = 'user-uuid'
        self.ari.set_channels(
            MockChannel(id=first_id),
            MockChannel(id=second_id),
            MockChannel(id=third_id),
            MockChannel(id=fourth_id),
        )
        self._set_channel_variable(
            {
                first_id: {'WAZO_USERUUID': user_uuid},
                second_id: {'WAZO_USERUUID': user_uuid},
                third_id: {'WAZO_USERUUID': user_uuid},
                fourth_id: {'WAZO_USERUUID': user_uuid},
            }
        )
        self.ari.set_applications(
            MockApplication(name='my-app', channels=[first_id, second_id, third_id])
        )
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{first_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appX', 'state': 'talking'}
                ),
                f'XIVO_CHANNELS_{second_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appY', 'state': 'talking'}
                ),
                f'XIVO_CHANNELS_{third_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'appX', 'state': 'talking'}
                ),
            }
        )
        calld_client = self.make_user_calld(user_uuid)

        calls = calld_client.calls.list_calls_from_user(
            application='my-app',
            application_instance='appX',
        )

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id),
                    has_entries(call_id=third_id),
                )
            ),
        )

    def test_given_local_channels_when_list_then_local_channels_are_ignored(self):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        user_uuid = 'user-uuid'
        self.ari.set_channels(
            MockChannel(id=first_id),
            MockChannel(id=second_id, name=SOME_LOCAL_CHANNEL_NAME),
        )
        self._set_channel_variable(
            {
                first_id: {'WAZO_USERUUID': user_uuid},
                second_id: {'WAZO_USERUUID': user_uuid},
            }
        )
        calld_client = self.make_user_calld(user_uuid)

        calls = calld_client.calls.list_calls_from_user()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=first_id),
                )
            ),
        )

    def test_extra_fields_on_user_calls(self):
        user_uuid = 'user-uuid'
        my_call = new_call_id()
        my_second_call = new_call_id(leap=1)
        self.ari.set_channels(
            MockChannel(
                id=my_call,
                channelvars={'CHANNEL(videonativeformat)': '(vp8|vp9)'},
            ),
            MockChannel(
                id=my_second_call,
                channelvars={'CHANNEL(videonativeformat)': '(nothing)'},
            ),
        )
        self._set_channel_variable(
            {
                my_call: {'WAZO_USERUUID': user_uuid},
                my_second_call: {'WAZO_USERUUID': user_uuid},
            }
        )
        self.confd.set_users(MockUser(uuid=user_uuid), MockUser(uuid='user2-uuid'))
        calld_client = self.make_user_calld(user_uuid)

        calls = calld_client.calls.list_calls_from_user()

        assert_that(
            calls,
            has_entries(
                items=contains_inanyorder(
                    has_entries(call_id=my_call, user_uuid=user_uuid, is_video=True),
                    has_entries(
                        call_id=my_second_call, user_uuid=user_uuid, is_video=False
                    ),
                )
            ),
        )


class TestGetCall(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_get_call_then_404(self):
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('not-found'),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_given_one_call_when_get_call_then_get_call(self):
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(
            MockChannel(
                id=first_id,
                state='Up',
                creation_time='first-time',
                caller_id_name='Weber',
                caller_id_number='4185559999',
            ),
            MockChannel(id=second_id),
        )
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=[first_id, second_id]))
        self._set_channel_variable(
            {
                first_id: {
                    'WAZO_USERUUID': 'user1-uuid',
                    'CHANNEL(channeltype)': 'PJSIP',
                    'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
                    'CHANNEL(videonativeformat)': '(vp8|vp9)',
                    'WAZO_LINE_ID': str(SOME_LINE_ID),
                },
                second_id: {'WAZO_USERUUID': 'user2-uuid'},
            }
        )
        self.confd.set_users(MockUser(uuid='user1-uuid'), MockUser(uuid='user2-uuid'))

        call = self.calld_client.calls.get_call(first_id)

        assert_that(
            call,
            has_entries(
                call_id=first_id,
                user_uuid='user1-uuid',
                status='Up',
                talking_to={second_id: 'user2-uuid'},
                bridges=contains_exactly('bridge-id'),
                creation_time='first-time',
                caller_id_name='Weber',
                caller_id_number='4185559999',
                sip_call_id='a-sip-call-id',
                line_id=SOME_LINE_ID,
                is_video=True,
            ),
        )

    def test_get_calls_tenant_isolation(
        self,
    ):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        tenant_uuid_1 = str(uuid.uuid4())
        tenant_uuid_2 = str(uuid.uuid4())
        first_id, second_id = new_call_id(), new_call_id(leap=1)
        self.ari.set_channels(MockChannel(id=first_id), MockChannel(id=second_id))
        self._set_channel_variable(
            {
                first_id: {'WAZO_TENANT_UUID': tenant_uuid_1},
                second_id: {'WAZO_TENANT_UUID': tenant_uuid_2},
            }
        )
        calld_1 = self.make_user_calld(user_uuid_1, tenant_uuid=tenant_uuid_1)
        calld_2 = self.make_user_calld(user_uuid_2, tenant_uuid=tenant_uuid_2)

        # tenant 1 call 1 = OK
        call = calld_1.calls.get_call(first_id)
        assert call['call_id'] == first_id
        # tenant 1 call 2 = NOK
        assert_that(
            calling(calld_1.calls.get_call).with_args(second_id),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        # tenant 2 call 1 = NOK
        assert_that(
            calling(calld_2.calls.get_call).with_args(first_id),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        # tenant 2 call 2 = OK
        call = calld_2.calls.get_call(second_id)
        assert call['call_id'] == second_id


class TestDeleteCall(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_delete_call_then_404(self):
        call_id = 'not-found'

        result = self.calld.delete_call_result(call_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_one_call_when_delete_call_then_call_hungup(self):
        call_id = 'call-id'
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))

        self.calld.hangup_call(call_id)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='DELETE',
                        path='/ari/channels/call-id',
                    )
                )
            ),
        )


class TestUserDeleteCall(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_delete_call_then_404(self):
        call_id = 'not-found'
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))

        result = self.calld.delete_user_me_call_result(call_id, token=token)

        assert_that(result.status_code, equal_to(404))

    def test_given_another_call_when_delete_call_then_403(self):
        call_id = new_call_id()
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))
        self._set_channel_variable({call_id: {'WAZO_USERUUID': 'some-other-uuid'}})

        result = self.calld.delete_user_me_call_result(call_id, token=token)

        assert_that(result.status_code, equal_to(403))
        assert_that(result.json(), has_entries(message=contains_string('user')))

    def test_given_my_call_when_delete_call_then_call_hungup(self):
        call_id = new_call_id()
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        self.ari.set_channels(
            MockChannel(
                id=call_id, state='Up', channelvars={'WAZO_USERUUID': user_uuid}
            ),
        )
        self._set_channel_variable({call_id: {'WAZO_USERUUID': user_uuid}})

        self.calld.hangup_my_call(call_id, token)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='DELETE',
                        path=f'/ari/channels/{call_id}',
                    )
                )
            ),
        )

    def test_local_channel_when_delete_call_then_call_hungup(self):
        call_id = new_call_id()
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        self.ari.set_channels(
            MockChannel(
                id=call_id,
                state='Up',
                name=SOME_LOCAL_CHANNEL_NAME,
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
        )
        self._set_channel_variable({call_id: {'WAZO_USERUUID': user_uuid}})

        result = self.calld.delete_user_me_call_result(call_id, token=token)

        assert_that(result.status_code, equal_to(404))


class TestCreateCall(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_create_call_with_correct_values(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(
            MockChannel(id=my_new_call_id, connected_line_number='')
        )
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        self._set_channel_variable(
            {
                my_new_call_id: {
                    'CHANNEL(channeltype)': 'PJSIP',
                    'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
                    'WAZO_LINE_ID': str(SOME_LINE_ID),
                }
            }
        )
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        result = self.calld_client.calls.make_call(call_args)

        assert_that(
            result,
            has_entries(
                call_id=my_new_call_id,
                dialed_extension='my-extension',
                peer_caller_id_number='my-extension',
                sip_call_id='a-sip-call-id',
                line_id=SOME_LINE_ID,
            ),
        )
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                    )
                )
            ),
        )

    def test_create_call_with_extension_containing_whitespace(self):
        user_uuid = 'user-uuid'
        priority = 1
        my_new_call_id = new_call_id()
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(
            MockChannel(id=my_new_call_id, connected_line_number='')
        )
        self.amid.set_valid_exten('my-context', '123456', priority)
        self._set_channel_variable(
            {
                my_new_call_id: {
                    'CHANNEL(channeltype)': 'PJSIP',
                    'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
                    'WAZO_LINE_ID': str(SOME_LINE_ID),
                }
            }
        )
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': '12 3\n4\t5\r6',
                'context': 'my-context',
            },
        }
        result = self.calld_client.calls.make_call(call_args)

        assert_that(
            result,
            has_entries(
                call_id=my_new_call_id,
                dialed_extension='123456',
                peer_caller_id_number='123456',
                sip_call_id='a-sip-call-id',
                line_id=SOME_LINE_ID,
            ),
        )
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                    )
                )
            ),
        )

    def test_when_create_call_then_ari_arguments_are_correct(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
            'variables': {
                'MY_VARIABLE': 'my-value',
                'SECOND_VARIABLE': 'my-second-value',
                'CONNECTEDLINE(name)': 'my-connected-line',
                'XIVO_FIX_CALLERID': '1',
            },
        }
        self.calld_client.calls.make_call(call_args)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=has_items(
                            ['priority', str(priority)],
                            ['extension', 'my-extension'],
                            ['context', 'my-context'],
                            ['endpoint', 'pjsip/line-name'],
                        ),
                        json=has_entries(
                            variables=has_entries(
                                {
                                    'MY_VARIABLE': 'my-value',
                                    'SECOND_VARIABLE': 'my-second-value',
                                    'CALLERID(name)': 'my-extension',
                                    'CALLERID(num)': 'my-extension',
                                    'CONNECTEDLINE(name)': 'my-connected-line',
                                    'CONNECTEDLINE(num)': 'my-extension',
                                    'XIVO_FIX_CALLERID': '1',
                                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                                }
                            )
                        ),
                    )
                )
            ),
        )

    def test_when_create_call_with_no_variables_then_default_variables_are_set(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        the_tenant_uuid = new_uuid()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['line-id'],
                tenant_uuid=the_tenant_uuid,
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        self.calld_client.calls.make_call(call_args)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        json=has_entries(
                            variables={
                                'WAZO_USERUUID': 'user-uuid',
                                '_WAZO_TENANT_UUID': the_tenant_uuid,
                                'CONNECTEDLINE(num)': 'my-extension',
                                'CONNECTEDLINE(name)': 'my-extension',
                                'CALLERID(name)': 'my-extension',
                                'CALLERID(num)': 'my-extension',
                                'XIVO_FIX_CALLERID': '1',
                                'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                            }
                        ),
                    )
                )
            ),
        )

    def test_when_create_call_with_pound_exten_then_connected_line_num_is_empty(self):
        '''
        This is a workaround for chan-sip bug that does not SIP-encode the pound sign
        in the SIP header To, causing Aastra phones to reject the INVITE.
        '''

        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', '#pound', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': '#pound',
                'context': 'my-context',
            },
        }
        self.calld_client.calls.make_call(call_args)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        json=has_entries(
                            variables=has_entries(
                                {
                                    'CONNECTEDLINE(num)': '',
                                    'CONNECTEDLINE(name)': '#pound',
                                    'CALLERID(name)': '#pound',
                                    'CALLERID(num)': '#pound',
                                }
                            )
                        ),
                    )
                )
            ),
        )

    def test_create_call_with_multiple_lines(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['line-id', 'line-id2'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        result = self.calld_client.calls.make_call(call_args)

        assert_that(result, has_entries(call_id=my_new_call_id))
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                    )
                )
            ),
        )

    def test_create_call_when_no_confd_then_503(self):
        priority = 1
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': 'userr-uuid'},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.calls.make_call).with_args(call_args),
                raises(CalldError).matching(
                    has_properties(
                        status_code=503,
                        error_id='wazo-confd-unreachable',
                    )
                ),
            )

    def test_create_call_with_no_lines(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', tenant_uuid='the-tenant-uuid'))
        self.confd.set_user_lines({'user-uuid': []})
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='user-missing-main-line',
                )
            ),
        )

    def test_create_call_with_invalid_user(self):
        user_uuid = 'user-uuid-not-found'
        priority = 1
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='invalid-user',
                )
            ),
        )

    def test_create_call_with_missing_source(self):
        self.amid.set_valid_exten('mycontext', 'myexten')
        call_args = {
            'destination': {
                'priority': '1',
                'extension': 'myexten',
                'context': 'mycontext',
            }
        }
        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    details=has_item('source'),
                )
            ),
        )

    def test_create_call_with_wrong_exten(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_no_valid_exten()
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'not-found',
                'context': 'my-context',
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    details=has_item('exten'),
                )
            ),
        )

    def test_create_call_with_no_content_type(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }

        with self.calld_client.calls_send_no_content_type():
            self.calld_client.calls.make_call(call_args)

    def test_create_call_with_explicit_line_not_found(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        line_id_not_found = 999999999999999999
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id', name='first-line-name', protocol=CONFD_SIP_PROTOCOL
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid, 'line_id': line_id_not_found},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='invalid-user-line',
                )
            ),
        )

    def test_create_call_with_explicit_wrong_line(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        unassociated_line_id = 987654321
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id', name='first-line-name', protocol=CONFD_SIP_PROTOCOL
            ),
            MockLine(
                id=unassociated_line_id,
                name='unassociated-line-name',
                protocol=CONFD_SIP_PROTOCOL,
            ),
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        call_args = {
            'source': {'user': user_uuid, 'line_id': unassociated_line_id},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='invalid-user-line',
                )
            ),
        )

    def test_create_call_with_explicit_line(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id', second_line_id],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id', name='first-line-name', protocol=CONFD_SIP_PROTOCOL
            ),
            MockLine(
                id=second_line_id, name='second-line-name', protocol=CONFD_SIP_PROTOCOL
            ),
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        call_args = {
            'source': {'user': user_uuid, 'line_id': second_line_id},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        self.calld_client.calls.make_call(call_args)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=has_items(
                            ['priority', str(priority)],
                            ['extension', 'my-extension'],
                            ['context', 'my-context'],
                            ['endpoint', 'pjsip/second-line-name'],
                        ),
                    )
                )
            ),
        )

    def test_create_call_all_lines(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id', second_line_id],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id', name='first-line-name', protocol=CONFD_SIP_PROTOCOL
            ),
            MockLine(
                id=second_line_id, name='second-line-name', protocol=CONFD_SIP_PROTOCOL
            ),
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        call_args = {
            'source': {'user': user_uuid, 'all_lines': True},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        self.calld_client.calls.make_call(call_args)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=has_items(
                            ['priority', str(priority)],
                            ['extension', 'my-extension'],
                            ['context', 'my-context'],
                            ['endpoint', 'local/user-uuid@usersharedlines'],
                        ),
                    )
                )
            ),
        )

    def test_create_call_all_lines_with_no_line(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', mobile='my-mobile', tenant_uuid='the-tenant-uuid'
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        call_args = {
            'source': {'user': user_uuid, 'from_mobile': True},
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='user-missing-main-line',
                )
            ),
        )

    def test_create_call_from_mobile_with_no_line(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', mobile='my-mobile', tenant_uuid='the-tenant-uuid'
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        call_args = {
            'source': {'user': user_uuid, 'from_mobile': True},
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='user-missing-main-line',
                )
            ),
        )

    def test_create_call_from_mobile_with_no_mobile(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        priority = 1
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-line-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        call_args = {
            'source': {'user': user_uuid, 'from_mobile': True},
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='call-creation',
                    message='User has no mobile phone number',
                )
            ),
        )

    def test_create_call_from_mobile_with_invalid_mobile(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                mobile='invalid',
                line_ids=['line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-line-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        call_args = {
            'source': {'user': user_uuid, 'from_mobile': True},
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='call-creation',
                    message='User has invalid mobile phone number',
                )
            ),
        )

    def test_create_call_from_mobile_to_wrong_extension(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten('my-line-context', 'my-mobile', priority)
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                mobile='my-mobile',
                line_ids=['line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-line-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        call_args = {
            'source': {'user': user_uuid, 'from_mobile': True},
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }

        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    error_id='invalid-extension',
                )
            ),
        )

    def test_create_call_auto_answer(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        my_new_call_id = new_call_id()
        priority = 1
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id', second_line_id],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id', name='first-line-name', protocol=CONFD_SIP_PROTOCOL
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        call_args = {
            'source': {'user': user_uuid, 'auto_answer': True},
            'destination': {
                'priority': priority,
                'extension': 'my-extension',
                'context': 'my-context',
            },
        }
        self.calld_client.calls.make_call(call_args)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        json=has_entries(
                            variables=has_entries(
                                {
                                    'PJSIP_HEADER(add,Alert-Info)': '<http://wazo.community>;info=alert-autoanswer;delay=0;xivo-autoanswer',
                                    'PJSIP_HEADER(add,Answer-After)': '0',
                                    'PJSIP_HEADER(add,Answer-Mode)': 'Auto',
                                    'PJSIP_HEADER(add,Call-Info)': ';answer-after=0',
                                    'PJSIP_HEADER(add,P-Auto-answer)': 'normal',
                                }
                            )
                        ),
                    )
                )
            ),
        )


class TestUserCreateCall(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_confd_when_create_then_503(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))

        body = {'extension': 'my-extension'}

        with self.confd_stopped():
            result = self.calld.post_user_me_call_result(body, token)

        assert_that(result.status_code, equal_to(503))

    def test_given_invalid_input_when_create_then_error_400(self):
        for invalid_body in self.invalid_call_requests():
            response = self.calld.post_user_me_call_result(invalid_body, VALID_TOKEN)

            assert_that(response.status_code, equal_to(400))
            assert_that(
                response.json(),
                has_entries(
                    message=contains_string('invalid'),
                    error_id=equal_to('invalid-data'),
                ),
            )

    def invalid_call_requests(self):
        valid_call_request = {'extension': '1234', 'variables': {'key': 'value'}}

        for key in ('extension', 'variables'):
            body: dict[str, Any] = dict(valid_call_request)
            body[key] = None
            yield body
            body[key] = 1234
            yield body
            body[key] = True
            yield body
            body[key] = ''
            yield body

        body = dict(valid_call_request)
        body.pop('extension')
        yield body

        body = dict(valid_call_request)
        body['variables'] = 'abcd'
        yield body

    def test_create_call_with_correct_values(self):
        user_uuid = 'user-uuid'
        my_new_call_id = new_call_id()
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid, line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(
            MockChannel(id=my_new_call_id, connected_line_number='')
        )
        self.amid.set_valid_exten('my-context', 'my-extension')

        result = self.calld.originate_me(extension='my-extension', token=token)

        assert_that(
            result,
            has_entries(
                call_id=my_new_call_id,
                dialed_extension='my-extension',
                peer_caller_id_number='my-extension',
            ),
        )
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                    )
                )
            ),
        )

    def test_create_call_with_extension_containing_whitespace(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid, line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(
            MockChannel(id=my_new_call_id, connected_line_number='')
        )
        self.amid.set_valid_exten('my-context', '123456')

        result = self.calld.originate_me(extension='12 3\n4\t5\r6', token=token)

        assert_that(
            result,
            has_entries(
                call_id=my_new_call_id,
                dialed_extension='123456',
                peer_caller_id_number='123456',
            ),
        )
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                    )
                )
            ),
        )

    def test_when_create_call_then_ari_arguments_are_correct(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid, line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(MockChannel(my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension')

        self.calld.originate_me(
            extension='my-extension',
            variables={
                'MY_VARIABLE': 'my-value',
                'SECOND_VARIABLE': 'my-second-value',
                'CONNECTEDLINE(name)': 'my-connected-line',
                'XIVO_FIX_CALLERID': '1',
            },
            token=token,
        )

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=has_items(
                            ['priority', '1'],
                            ['extension', 'my-extension'],
                            ['context', 'my-context'],
                            ['endpoint', 'pjsip/line-name'],
                        ),
                        json=has_entries(
                            variables=has_entries(
                                {
                                    'MY_VARIABLE': 'my-value',
                                    'SECOND_VARIABLE': 'my-second-value',
                                    'CONNECTEDLINE(name)': 'my-connected-line',
                                    'CONNECTEDLINE(num)': 'my-extension',
                                    'CALLERID(name)': 'my-extension',
                                    'CALLERID(num)': 'my-extension',
                                    'XIVO_FIX_CALLERID': '1',
                                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                                }
                            )
                        ),
                    )
                )
            ),
        )

    def test_when_create_call_with_no_variables_then_default_variables_are_set(self):
        user_uuid = 'user-uuid'
        the_tenant_uuid = new_uuid()
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid,
                line_ids=['line-id'],
                tenant_uuid=the_tenant_uuid,
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension')

        self.calld.originate_me(extension='my-extension', token=token)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        json=has_entries(
                            variables={
                                'WAZO_USERUUID': 'user-uuid',
                                '_WAZO_TENANT_UUID': the_tenant_uuid,
                                'CONNECTEDLINE(name)': 'my-extension',
                                'CONNECTEDLINE(num)': 'my-extension',
                                'CALLERID(name)': 'my-extension',
                                'CALLERID(num)': 'my-extension',
                                'XIVO_FIX_CALLERID': '1',
                                'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                            }
                        ),
                    )
                )
            ),
        )

    def test_create_call_with_multiple_lines(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid,
                line_ids=['line-id', 'line-id2'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension')

        result = self.calld.originate_me(extension='my-extension', token=token)

        assert_that(result, has_entries(call_id=my_new_call_id))
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                    )
                )
            ),
        )

    def test_create_call_with_no_lines(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', tenant_uuid='the-tenant-uuid'))
        self.confd.set_user_lines({'user-uuid': []})
        self.amid.set_valid_exten('my-context', 'my-extension')

        body = {'extension': 'my-extension'}
        result = self.calld.post_user_me_call_result(body, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('line'))

    def test_create_call_with_invalid_user(self):
        user_uuid = 'user-uuid-not-found'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.amid.set_valid_exten('my-context', 'my-extension')

        body = {'extension': 'my-extension'}
        result = self.calld.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_create_call_with_wrong_exten(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid, line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_no_valid_exten()

        body = {'extension': 'not-found'}
        result = self.calld.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('exten'))

    def test_create_call_with_unknown_confd_context(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id']))
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension')

        body = {'extension': 'not-found'}
        result = self.calld.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('exten'))

    def test_create_call_with_no_content_type(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid=user_uuid, line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='my-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('my-context', 'my-extension')
        self.calld_client.set_token(token)

        with self.calld_client.calls_send_no_content_type():
            self.calld_client.calls.make_call_from_user(extension='my-extension')

    def test_create_call_with_explicit_line(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        my_new_call_id = new_call_id()
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id', second_line_id],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id',
                name='first-line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='first-context',
            ),
            MockLine(
                id=second_line_id,
                name='second-line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='second-context',
            ),
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('second-context', 'my-extension')

        self.calld.originate_me('my-extension', line_id=second_line_id, token=token)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=has_items(
                            ['priority', '1'],
                            ['extension', 'my-extension'],
                            ['context', 'second-context'],
                            ['endpoint', 'pjsip/second-line-name'],
                        ),
                    )
                )
            ),
        )

    def test_create_call_all_lines(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id', second_line_id],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id',
                name='first-line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='first-context',
            ),
            MockLine(
                id=second_line_id,
                name='second-line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='second-context',
            ),
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('first-context', 'my-extension')

        self.calld.originate_me('my-extension', all_lines=True, token=token)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=has_items(
                            ['priority', '1'],
                            ['extension', 'my-extension'],
                            ['context', 'first-context'],
                            ['endpoint', 'local/user-uuid@usersharedlines'],
                        ),
                    )
                )
            ),
        )

    def test_create_call_auto_answer(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        token = 'my-token'
        my_new_call_id = new_call_id()
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                line_ids=['first-line-id', second_line_id],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='first-line-id',
                name='first-line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context='first-context',
            )
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))
        self.amid.set_valid_exten('first-context', 'my-extension')

        self.calld.originate_me('my-extension', token=token, auto_answer_caller=True)

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        json=has_entries(
                            variables=has_entries(
                                {
                                    'PJSIP_HEADER(add,Alert-Info)': '<http://wazo.community>;info=alert-autoanswer;delay=0;xivo-autoanswer',
                                    'PJSIP_HEADER(add,Answer-After)': '0',
                                    'PJSIP_HEADER(add,Answer-Mode)': 'Auto',
                                    'PJSIP_HEADER(add,Call-Info)': ';answer-after=0',
                                    'PJSIP_HEADER(add,P-Auto-answer)': 'normal',
                                }
                            )
                        ),
                    )
                )
            ),
        )


class TestFailingARI(_BaseTestCalls):
    asset = 'failing_ari'
    wait_strategy = CalldUpWaitStrategy()

    def setUp(self):
        super().setUp()
        self.confd.reset()

    def test_given_no_ari_when_list_calls_then_503(self):
        assert_that(
            calling(self.calld_client.calls.list_calls),
            raises(CalldError).matching(
                has_properties(
                    status_code=503,
                    error_id='asterisk-ari-error',
                )
            ),
        )

    def test_given_no_ari_when_get_call_then_503(self):
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('id'),
            raises(CalldError).matching(
                has_properties(
                    status_code=503,
                    error_id='asterisk-ari-error',
                )
            ),
        )

    def test_given_no_ari_when_originate_then_503(self):
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.amid.set_valid_exten('context', 'extension')
        call_args = {
            'source': {'user': 'user-uuid'},
            'destination': {
                'priority': SOME_PRIORITY,
                'extension': 'extension',
                'context': 'context',
            },
        }
        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call_args),
            raises(CalldError).matching(
                has_properties(
                    status_code=503,
                    error_id='asterisk-ari-error',
                )
            ),
        )

    def test_given_no_ari_when_delete_call_then_503(self):
        assert_that(
            calling(self.calld_client.calls.hangup).with_args('call-id'),
            raises(CalldError).matching(
                has_properties(
                    status_code=503,
                    error_id='asterisk-ari-error',
                )
            ),
        )


class TestConnectUser(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_one_call_and_one_user_when_connect_user_then_the_two_are_talking(
        self,
    ):
        call_id = new_call_id()
        my_new_call_id = new_call_id(leap=1)
        self.ari.set_channels(
            MockChannel(id=call_id),
            MockChannel(id=my_new_call_id),
        )
        self._set_channel_variable({my_new_call_id: {'WAZO_USERUUID': 'user-uuid'}})
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{call_id}': json.dumps(
                    {'app': 'sw', 'app_instance': 'sw1', 'state': 'ringing'}
                )
            }
        )
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))

        new_call = self.calld_client.calls.connect_user(call_id, 'user-uuid')

        assert_that(new_call, has_entries(call_id=my_new_call_id))

        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_items(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=contains_inanyorder(
                            ['app', 'callcontrol'],
                            ['endpoint', 'pjsip/line-name'],
                            ['appArgs', f'sw1,dialed_from,{call_id}'],
                            ['timeout', '30'],
                            ['originator', call_id],
                        ),
                    )
                )
            ),
        )

    def test_one_call_one_user_with_timeout(
        self,
    ):
        call_id = new_call_id()
        my_new_call_id = new_call_id(leap=1)
        self.ari.set_channels(
            MockChannel(id=call_id),
            MockChannel(id=my_new_call_id),
        )
        self._set_channel_variable({my_new_call_id: {'WAZO_USERUUID': 'user-uuid'}})
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{call_id}': json.dumps(
                    {'app': 'sw', 'app_instance': 'sw1', 'state': 'ringing'}
                )
            }
        )
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )
        self.ari.set_originates(MockChannel(id=my_new_call_id))

        new_call = self.calld_client.calls.connect_user(call_id, 'user-uuid', timeout=1)

        assert_that(new_call, has_entries(call_id=my_new_call_id))
        assert_that(
            self.ari.requests(),
            has_entries(
                requests=has_items(
                    has_entries(
                        method='POST',
                        path='/ari/channels',
                        query=contains_inanyorder(
                            ['app', 'callcontrol'],
                            ['endpoint', 'pjsip/line-name'],
                            ['appArgs', f'sw1,dialed_from,{call_id}'],
                            ['timeout', '1'],
                            ['originator', call_id],
                        ),
                    )
                )
            ),
        )

    def test_given_no_confd_when_connect_user_then_503(self):
        with self.confd_stopped():
            with pytest.raises(CalldError) as exc_info:
                self.calld_client.calls.connect_user(
                    'call-id', 'user-uuid', token=VALID_TOKEN
                )

        calld_error = exc_info.value
        assert_that(calld_error.status_code, equal_to(503))

    def test_given_no_user_when_connect_user_then_400(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))

        with pytest.raises(CalldError) as exc_info:
            self.calld_client.calls.connect_user(
                call_id, 'user-uuid', token=VALID_TOKEN
            )

        calld_error = exc_info.value
        assert_that(calld_error.status_code, equal_to(400))
        assert_that(calld_error.message.lower(), contains_string('user'))

    def test_given_user_has_no_line_when_connect_user_then_400(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.confd.set_users(MockUser(uuid='user-uuid'))

        with pytest.raises(CalldError) as exc_info:
            self.calld_client.calls.connect_user(
                call_id, 'user-uuid', token=VALID_TOKEN
            )

        calld_error = exc_info.value
        assert_that(calld_error.status_code, equal_to(400))
        assert_that(calld_error.message.lower(), contains_string('user'))

    def test_given_no_call_when_connect_user_then_404(self):
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(
            MockLine(id='line-id', name='line-name', protocol=CONFD_SIP_PROTOCOL)
        )

        with pytest.raises(CalldError) as exc_info:
            self.calld_client.calls.connect_user(
                'call-id', 'user-uuid', token=VALID_TOKEN
            )

        calld_error = exc_info.value
        assert_that(calld_error.status_code, equal_to(404))
        assert_that(calld_error.message.lower(), contains_string('call'))


class TestCallerID(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_when_create_call_and_answer1_then_connected_line_is_correct(self):
        self.confd.set_users(
            MockUser(
                uuid='user-uuid', line_ids=['line-id'], tenant_uuid='the-tenant-uuid'
            )
        )
        self.confd.set_lines(MockLine(id='line-id', name='originator', protocol='test'))
        call_args = {
            'source': {'user': 'user-uuid'},
            'destination': {
                'priority': 1,
                'extension': 'ring-connected-line',
                'context': 'local',
            },
        }
        originator_call = self.calld_client.calls.make_call(call_args)
        originator_channel = self.ari.channels.get(channelId=originator_call['call_id'])
        recipient_caller_id_name = 'rêcîpîênt'
        recipient_caller_id_number = 'ring-connected-line'
        bus_events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.chan_test.answer_channel(originator_channel.id)

        def originator_has_correct_connected_line(name, number):
            expected_peer_caller_id = {'name': name, 'number': number}
            peer_caller_ids = [
                {
                    'name': message['data']['peer_caller_id_name'],
                    'number': message['data']['peer_caller_id_number'],
                }
                for message in bus_events.accumulate()
                if message['data']['call_id'] == originator_channel.id
            ]

            return expected_peer_caller_id in peer_caller_ids

        until.true(
            originator_has_correct_connected_line,
            recipient_caller_id_name,
            recipient_caller_id_number,
            tries=10,
        )


class TestUserCreateCallFromMobile(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_create_call_from_mobile(self):
        user_uuid = 'user-uuid'
        mobile_context, mobile_extension = 'local', 'mobile'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                mobile=mobile_extension,
                line_ids=['line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context=mobile_context,
            )
        )

        result = self.calld.originate_me('recipient', from_mobile=True, token=token)

        result_channel = self.ari.channels.get(channelId=result['call_id'])
        assert_that(result_channel.json['name'], not_(starts_with('Local')))

    def test_given_mobile_does_not_dial_when_user_create_call_from_mobile_then_400(
        self,
    ):
        user_uuid = 'user-uuid'
        mobile_context, mobile_extension = 'local', 'mobile-no-dial'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                mobile=mobile_extension,
                line_ids=['line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context=mobile_context,
            )
        )

        result = self.calld.post_user_me_call_result(
            {'extension': 'recipient', 'from_mobile': True}, token=token
        )

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('dial'))

    def test_create_call_from_mobile_overrides_line_id(self):
        user_uuid = 'user-uuid'
        mobile_context, mobile_extension = 'local', 'mobile'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(
            MockUser(
                uuid='user-uuid',
                mobile=mobile_extension,
                line_ids=['line-id'],
                tenant_uuid='the-tenant-uuid',
            )
        )
        self.confd.set_lines(
            MockLine(
                id='line-id',
                name='line-name',
                protocol=CONFD_SIP_PROTOCOL,
                context=mobile_context,
            )
        )

        result = self.calld.originate_me('recipient', from_mobile=True, token=token)

        result_channel = self.ari.channels.get(channelId=result['call_id'])
        assert_that(result_channel.json['name'], starts_with('Test/integration-mobile'))


class TestCallMute(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_put_mute_start(self):
        channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.start_mute).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.start_mute(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id,
                                muted=True,
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, muted=True)),
        )

    def test_put_mute_start_from_user(self):
        user_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        other_channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.start_mute_from_user).with_args(
                UNKNOWN_UUID
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.calls.start_mute_from_user).with_args(
                other_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.start_mute_from_user(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id,
                                muted=True,
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, muted=True)),
        )

    def test_put_mute_stop(self):
        channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.stop_mute).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.stop_mute(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id,
                                muted=False,
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, muted=False)),
        )

    def test_put_mute_stop_from_user(self):
        user_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        other_channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.stop_mute_from_user).with_args(
                UNKNOWN_UUID
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.calls.stop_mute_from_user).with_args(
                other_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.stop_mute_from_user(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id,
                                muted=False,
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, muted=False)),
        )

    def given_call_not_stasis(self, user_uuid=None):
        user_uuid = user_uuid or str(uuid.uuid4())
        call = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='local',
            extension='dial-autoanswer',
            variables={
                'variables': {
                    'WAZO_USERUUID': user_uuid,
                    '__WAZO_TENANT_UUID': VALID_TENANT,
                }
            },
        )
        return call.id

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        return token


class TestCallSendDTMF(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_put_dtmf(self):
        user_uuid = str(uuid.uuid4())
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.send_dtmf_digits).with_args(
                UNKNOWN_UUID, '1234'
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Invalid DTMF
        assert_that(
            calling(self.calld_client.calls.send_dtmf_digits).with_args(
                channel_id, 'invalid'
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

        event_accumulator = self.bus.accumulator(headers={'name': 'DTMFEnd'})

        # Valid DTMF
        test_str = '12*#'
        self.calld_client.calls.send_dtmf_digits(channel_id, test_str)

        def amid_dtmf_events_received():
            events = event_accumulator.accumulate(with_headers=True)
            for expected_digit in test_str:
                assert_that(
                    events,
                    has_item(
                        has_entries(
                            message=has_entries(
                                name='DTMFEnd',
                                data=has_entries(
                                    Direction='Received',
                                    Digit=expected_digit,
                                    Uniqueid=channel_id,
                                ),
                            ),
                            headers=has_entries(
                                name='DTMFEnd',
                            ),
                        )
                    ),
                )

        until.assert_(amid_dtmf_events_received, tries=10)

    def test_put_dtmf_from_user(self):
        user_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        other_channel_id = self.given_call_not_stasis()

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.send_dtmf_digits_from_user).with_args(
                UNKNOWN_UUID, '1234'
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Wrong user channel ID
        assert_that(
            calling(self.calld_client.calls.send_dtmf_digits_from_user).with_args(
                other_channel_id, '1234'
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        event_accumulator = self.bus.accumulator(headers={'name': 'DTMFEnd'})

        # Valid DTMF
        test_str = '12*#'
        self.calld_client.calls.send_dtmf_digits(channel_id, test_str)

        def amid_dtmf_events_received():
            events = event_accumulator.accumulate(with_headers=True)
            for expected_digit in test_str:
                assert_that(
                    events,
                    has_item(
                        has_entries(
                            message=has_entries(
                                name='DTMFEnd',
                                data=has_entries(
                                    Direction='Received',
                                    Digit=expected_digit,
                                    Uniqueid=channel_id,
                                ),
                            ),
                            headers=has_entries(
                                name='DTMFEnd',
                            ),
                        )
                    ),
                )

        until.assert_(amid_dtmf_events_received, tries=10)

    def given_call_not_stasis(self, user_uuid=None):
        user_uuid = user_uuid or str(uuid.uuid4())
        call = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='local',
            extension='dial-autoanswer',
            variables={
                'variables': {
                    'WAZO_USERUUID': user_uuid,
                    '__WAZO_TENANT_UUID': VALID_TENANT,
                }
            },
        )
        return call.id

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        return token


class TestCallHold(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.phoned.reset()

    def test_hold(self):
        first_id = new_call_id()
        self.ari.set_channels(
            MockChannel(id=first_id, state='Up', name='PJSIP/abcdef-000001'),
            MockChannel(
                id='second-id-no-device', state='Up', name='PJSIP/not-found-000002'
            ),
            MockChannel(
                id='third-id-no-device-plugin',
                state='Up',
                name='PJSIP/no-plugin-000003',
            ),
        )

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.start_hold).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Channel device is not found on phoned
        assert_that(
            calling(self.calld_client.calls.start_hold).with_args(
                'second-id-no-device'
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Channel device has no plugin on phoned
        assert_that(
            calling(self.calld_client.calls.start_hold).with_args(
                'third-id-no-device-plugin'
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Hold
        self.calld_client.calls.start_hold(first_id)

        assert_that(
            self.phoned.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='PUT',
                        path='/0.1/endpoints/abcdef/hold/start',
                    )
                )
            ),
        )

    def test_unhold(self):
        first_id = new_call_id()
        self.ari.set_channels(
            MockChannel(id=first_id, state='Up', name='PJSIP/abcdef-000001'),
            MockChannel(
                id='second-id-no-device', state='Up', name='PJSIP/not-found-000002'
            ),
            MockChannel(
                id='third-id-no-device-plugin',
                state='Up',
                name='PJSIP/no-plugin-000003',
            ),
        )

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.stop_hold).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Channel device is not found on phoned
        assert_that(
            calling(self.calld_client.calls.stop_hold).with_args('second-id-no-device'),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Channel device has no plugin on phoned
        assert_that(
            calling(self.calld_client.calls.stop_hold).with_args(
                'third-id-no-device-plugin'
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Unhold
        self.calld_client.calls.stop_hold(first_id)

        assert_that(
            self.phoned.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='PUT',
                        path='/0.1/endpoints/abcdef/hold/stop',
                    )
                )
            ),
        )

    def test_user_hold(self):
        user_channel_id = new_call_id()
        someone_else_channel_id = new_call_id(leap=1)
        user_channel_id_device_no_plugin = new_call_id(leap=2)
        user_channel_id_no_device = new_call_id(leap=3)
        user_uuid = str(uuid.uuid4())
        someone_else_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        self.ari.set_channels(
            MockChannel(
                id=user_channel_id,
                state='Up',
                name='PJSIP/abcdef-000001',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
            MockChannel(
                id=someone_else_channel_id,
                state='Up',
                name='PJSIP/ghijkl-000002',
                channelvars={'WAZO_USERUUID': someone_else_uuid},
            ),
            MockChannel(
                id=user_channel_id_device_no_plugin,
                state='Up',
                name='PJSIP/no-plugin-000003',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
            MockChannel(
                id=user_channel_id_no_device,
                state='Up',
                name='PJSIP/not-found-000004',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
        )
        self._set_channel_variable(
            {
                user_channel_id: {'WAZO_USERUUID': user_uuid},
                someone_else_channel_id: {'WAZO_USERUUID': someone_else_uuid},
                user_channel_id_device_no_plugin: {'WAZO_USERUUID': user_uuid},
                user_channel_id_no_device: {'WAZO_USERUUID': user_uuid},
            }
        )

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.start_hold_from_user).with_args(
                UNKNOWN_UUID
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Unauthorized channel
        assert_that(
            calling(self.calld_client.calls.start_hold_from_user).with_args(
                someone_else_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # Channel device is not found on phoned
        assert_that(
            calling(self.calld_client.calls.start_hold_from_user).with_args(
                user_channel_id_no_device
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Channel device has no plugin on phoned
        assert_that(
            calling(self.calld_client.calls.start_hold_from_user).with_args(
                user_channel_id_device_no_plugin
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Hold
        self.calld_client.calls.start_hold_from_user(user_channel_id)

        assert_that(
            self.phoned.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='PUT',
                        path='/0.1/endpoints/abcdef/hold/start',
                    )
                )
            ),
        )

    def test_user_unhold(self):
        user_channel_id = new_call_id()
        someone_else_channel_id = new_call_id(leap=1)
        user_channel_id_device_no_plugin = new_call_id(leap=2)
        user_channel_id_no_device = new_call_id(leap=3)
        user_uuid = str(uuid.uuid4())
        someone_else_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        self.ari.set_channels(
            MockChannel(
                id=user_channel_id,
                state='Up',
                name='PJSIP/abcdef-000001',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
            MockChannel(
                id=someone_else_channel_id,
                state='Up',
                name='PJSIP/ghijkl-000002',
                channelvars={'WAZO_USERUUID': someone_else_uuid},
            ),
            MockChannel(
                id=user_channel_id_device_no_plugin,
                state='Up',
                name='PJSIP/no-plugin-000003',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
            MockChannel(
                id=user_channel_id_no_device,
                state='Up',
                name='PJSIP/not-found-000004',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
        )
        self._set_channel_variable(
            {
                user_channel_id: {'WAZO_USERUUID': user_uuid},
                someone_else_channel_id: {'WAZO_USERUUID': someone_else_uuid},
                user_channel_id_device_no_plugin: {'WAZO_USERUUID': user_uuid},
                user_channel_id_no_device: {'WAZO_USERUUID': user_uuid},
            }
        )

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.stop_hold_from_user).with_args(
                UNKNOWN_UUID
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Unauthorized channel
        assert_that(
            calling(self.calld_client.calls.stop_hold_from_user).with_args(
                someone_else_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # Channel device is not found on phoned
        assert_that(
            calling(self.calld_client.calls.stop_hold_from_user).with_args(
                user_channel_id_no_device
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Channel device has no plugin on phoned
        assert_that(
            calling(self.calld_client.calls.stop_hold_from_user).with_args(
                user_channel_id_device_no_plugin
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Unhold
        self.calld_client.calls.stop_hold_from_user(user_channel_id)

        assert_that(
            self.phoned.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='PUT',
                        path='/0.1/endpoints/abcdef/hold/stop',
                    )
                )
            ),
        )

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        return token


class TestCallAnswer(_BaseTestCalls):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.phoned.reset()

    def test_answer(self):
        first_id = new_call_id()
        self.ari.set_channels(
            MockChannel(id=first_id, state='Up', name='PJSIP/abcdef-000001'),
            MockChannel(
                id='second-id-no-device', state='Up', name='PJSIP/not-found-000002'
            ),
            MockChannel(
                id='third-id-no-device-plugin',
                state='Up',
                name='PJSIP/no-plugin-000003',
            ),
        )

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.answer).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Channel device is not found on phoned
        assert_that(
            calling(self.calld_client.calls.answer).with_args('second-id-no-device'),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Channel device has no plugin on phoned
        assert_that(
            calling(self.calld_client.calls.answer).with_args(
                'third-id-no-device-plugin'
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Answer
        self.calld_client.calls.answer(first_id)

        assert_that(
            self.phoned.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='PUT',
                        path='/0.1/endpoints/abcdef/answer',
                    )
                )
            ),
        )

    def test_user_answer(self):
        user_uuid = str(uuid.uuid4())
        someone_else_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        user_channel_id = new_call_id()
        someone_else_channel_id = new_call_id(leap=1)
        user_channel_id_device_no_plugin = new_call_id(leap=2)
        user_channel_id_no_device = new_call_id(leap=3)
        self.calld_client.set_token(token)
        self.ari.set_channels(
            MockChannel(
                id=user_channel_id,
                state='Up',
                name='PJSIP/abcdef-000001',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
            MockChannel(
                id=someone_else_channel_id,
                state='Up',
                name='PJSIP/ghijkl-000002',
                channelvars={'WAZO_USERUUID': someone_else_uuid},
            ),
            MockChannel(
                id=user_channel_id_device_no_plugin,
                state='Up',
                name='PJSIP/no-plugin-000003',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
            MockChannel(
                id=user_channel_id_no_device,
                state='Up',
                name='PJSIP/not-found-000004',
                channelvars={'WAZO_USERUUID': user_uuid},
            ),
        )
        self._set_channel_variable(
            {
                user_channel_id: {'WAZO_USERUUID': user_uuid},
                someone_else_channel_id: {'WAZO_USERUUID': someone_else_uuid},
                user_channel_id_device_no_plugin: {'WAZO_USERUUID': user_uuid},
                user_channel_id_no_device: {'WAZO_USERUUID': user_uuid},
            }
        )

        # Invalid channel ID
        assert_that(
            calling(self.calld_client.calls.answer_from_user).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Unauthorized channel
        assert_that(
            calling(self.calld_client.calls.answer_from_user).with_args(
                someone_else_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # Channel device is not found on phoned
        assert_that(
            calling(self.calld_client.calls.answer_from_user).with_args(
                user_channel_id_no_device
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Channel device has no plugin on phoned
        assert_that(
            calling(self.calld_client.calls.answer_from_user).with_args(
                user_channel_id_device_no_plugin
            ),
            raises(CalldError).matching(has_properties(status_code=503)),
        )

        # Answer
        self.calld_client.calls.answer_from_user(user_channel_id)

        assert_that(
            self.phoned.requests(),
            has_entries(
                requests=has_item(
                    has_entries(
                        method='PUT',
                        path='/0.1/endpoints/abcdef/answer',
                    )
                )
            ),
        )

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        return token


class TestPickup(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)
        self.real_asterisk = RealAsterisk(self.ari, self.calld_client)

    def test_pickup_hangup(self):
        caller_uuid = str(uuid.uuid4())
        callee_uuid = str(uuid.uuid4())
        interceptor_uuid = str(uuid.uuid4())
        user_calld_client = self.make_user_calld(
            interceptor_uuid, tenant_uuid=VALID_TENANT
        )
        (
            caller_channel_id,
            callee_channel_id,
        ) = self.real_asterisk.given_ringing_call_not_stasis(caller_uuid, callee_uuid)

        interceptor_channel_id = self.real_asterisk.pickup(interceptor_uuid)

        def pickup_finished():
            assert_that(caller_channel_id, self.c.is_talking(), 'caller is not talking')
            assert_that(
                callee_channel_id, self.c.is_hungup(), 'callee is still talking'
            )
            assert_that(
                interceptor_channel_id,
                self.c.is_talking(),
                'interceptor is not talking',
            )
            assert_that(
                interceptor_channel_id,
                self.c.has_variable('WAZO_USERUUID', interceptor_uuid),
            )

        # wazo-calld needs some delay to process the Pickup event and allowing hangup
        until.assert_(pickup_finished, timeout=3, message='Pickup failed')

        user_calld_client.calls.hangup_from_user(interceptor_channel_id)

        def pickup_hungup():
            assert_that(
                caller_channel_id,
                self.c.is_hungup(),
                'caller channel is still talking',
            )
            assert_that(
                interceptor_channel_id,
                self.c.is_hungup(),
                'interceptor channel is still talking',
            )

        until.assert_(pickup_hungup, timeout=3, message='Hangup failed')
