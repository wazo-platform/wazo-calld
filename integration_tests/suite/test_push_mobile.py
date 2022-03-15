# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    contains,
    has_item,
    has_entries,
)

from wazo_amid_client import Client as AmidClient
from wazo_test_helpers import until

from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.constants import VALID_TOKEN_MULTITENANT


class TestPushMobile(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.amid = AmidClient(
            'localhost',
            port=self.service_port(9491, 'amid'),
            https=False,
            prefix=None,
            token=VALID_TOKEN_MULTITENANT,
        )

    def test_send_push_mobile(self):
        events = self.bus.accumulator('calls.call.push_notification')

        push_mobile_event = {
            'data': {
                'UserEvent': 'Pushmobile',
                'Uniqueid': '1560784195.313',
                'ChanVariable': {
                    'XIVO_BASE_EXTEN': '8000',
                    'WAZO_DEREFERENCED_USERUUID': '',
                    'XIVO_USERUUID': 'eaa18a7f-3f49-419a-9abb-b445b8ba2e03',
                    'WAZO_TENANT_UUID': 'some-tenant-uuid',
                },
                'CallerIDName': 'my name is 8001',
                'Event': 'UserEvent',
                'WAZO_DST_UUID': 'fb27eb93-d21c-483f-8068-e685c90b07e1',
                'WAZO_VIDEO_ENABLED': '1',
                'ConnectedLineName': 'bob 8000',
                'Priority': '2',
                'ChannelStateDesc': 'Ring',
                'Language': 'en_US',
                'CallerIDNum': '8001',
                'Exten': 's',
                'ChannelState': '4',
                'Channel': 'PJSIP/cfy381cl-00000139',
                'Context': 'wazo-user-mobile-notification',
                'Linkedid': '1560784195.313',
                'ConnectedLineNum': '8000',
                'Privilege': 'user,all',
                'AccountCode': '',
            }
        }

        self.bus.publish(push_mobile_event, routing_key='ami.UserEvent')

        def bus_events_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            name='call_push_notification',
                            data=has_entries(
                                peer_caller_id_number='8001',
                                peer_caller_id_name='my name is 8001',
                                call_id='1560784195.313',
                                video=True,
                            ),
                            required_acl='events.calls.fb27eb93-d21c-483f-8068-e685c90b07e1',
                        ),
                        headers=has_entries({
                            'name': 'call_push_notification',
                            'tenant_uuid': 'some-tenant-uuid',
                            'user_uuid:fb27eb93-d21c-483f-8068-e685c90b07e1': True,
                        })
                    )
                )
            )

        until.assert_(bus_events_received, timeout=10)

    def test_user_hint_is_updated_on_mobile_session(self):
        user_uuid = 'eaa18a7f-3f49-419a-9abb-b445b8ba2e03'
        tenant_uuid = 'some-tenant-uuid'

        self.bus.publish(
            {
                'name': 'auth_user_sessions_updated',
                'data': {
                    'user_uuid': user_uuid,
                    'tenant_uuid': tenant_uuid,
                    'sessions': [
                        {'uuid': 'session-uuid', 'mobile': True},
                    ],
                },
            },
            routing_key=f'auth.users.{user_uuid}.sessions.updated',
        )

        def user_hint_updated():
            result = self.amid.action('Getvar', {'Variable': f'DEVICE_STATE(Custom:{user_uuid})'})
            assert_that(result, contains(has_entries(
                Response='Success',
                Value='NOT_INUSE',
            )))

        until.assert_(user_hint_updated, timeout=10)

        self.bus.publish(
            {
                'name': 'auth_user_sessions_updated',
                'data': {
                    'user_uuid': user_uuid,
                    'tenant_uuid': tenant_uuid,
                    'sessions': [],
                },
            },
            routing_key=f'auth.users.{user_uuid}.sessions.updated',
        )

        def user_hint_updated():
            result = self.amid.action('Getvar', {'Variable': f'DEVICE_STATE(Custom:{user_uuid})'})
            assert_that(result, contains(has_entries(
                Response='Success',
                Value='UNAVAILABLE',
            )))

        until.assert_(user_hint_updated, timeout=10)
