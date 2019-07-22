# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    contains,
    has_entries,
)

from xivo_test_helpers import until

from .helpers.base import RealAsteriskIntegrationTest


class TestPushMobile(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def test_send_push_mobile(self):
        events = self.bus.accumulator('calls.call.push_notification')

        push_mobile_event = {
            'data': {
                'UserEvent': 'Pushmobile',
                'Uniqueid': '1560784195.313',
                'ChanVariable': {'XIVO_BASE_EXTEN': '8000',
                                 'WAZO_DEREFERENCED_USERUUID': '',
                                 'XIVO_USERUUID': 'eaa18a7f-3f49-419a-9abb-b445b8ba2e03'},
                'CallerIDName': 'my name is 8001',
                'Event': 'UserEvent',
                'WAZO_DST_UUID': 'fb27eb93-d21c-483f-8068-e685c90b07e1',
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
            assert_that(events.accumulate(), contains(
                has_entries(
                    name='call_push_notification',
                    data=has_entries(
                        peer_caller_id_number='8001',
                        peer_caller_id_name='my name is 8001',
                    ),
                    required_acl='events.calls.fb27eb93-d21c-483f-8068-e685c90b07e1',
                ),
            ))

        until.assert_(bus_events_received, timeout=3)
