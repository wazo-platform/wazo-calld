# Copyright 2024-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from uuid import uuid4

from ari.exceptions import ARINotFound
from hamcrest import assert_that, has_entries, has_item
from wazo_test_helpers import until

from .helpers.constants import ENDPOINT_AUTOANSWER
from .helpers.real_asterisk import RealAsteriskIntegrationTest


class TestDialMobile(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_that_dial_mobile_join_with_no_bridge_does_not_block(self):
        unknown_bridge_id = str(uuid4())
        channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app='dial_mobile',
            appArgs=['join', unknown_bridge_id],
        )

        def channel_is_gone(ari, channel_id):
            try:
                ari.channels.get(channelId=channel_id)
                return False
            except ARINotFound:
                return True

        until.true(
            channel_is_gone,
            self.ari,
            channel.id,
            timeout=10,
            message='Channel is stuck in stasis',
        )

    def test_caller_hangup_cancels_push_notification(self):
        # Regression test: when caller hangs up while waiting for mobile to
        # register, the pending push notification must be cancelled.
        push_events = self.bus.accumulator(headers={'name': 'call_push_notification'})
        cancel_events = self.bus.accumulator(
            headers={'name': 'call_cancel_push_notification'}
        )

        # Originate a channel into dial_mobile 'dial' path; for a fresh
        # ARI-originated channel CHANNEL(linkedid) == channel Uniqueid.
        # StasisStart is processed before we publish to the bus, so
        # dial_all_contacts will have run by the time we wait for the push event.
        chan = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app='dial_mobile',
            appArgs=['dial', 'nonexistent-aor'],
        )

        # Wait until the channel is in Stasis (Up state means autoanswer fired).
        def channel_is_up():
            ch = self.ari.channels.get(channelId=chan.id)
            assert ch.json['state'] == 'Up'

        until.assert_(
            channel_is_up, timeout=5, message='Channel never reached Up state'
        )

        # Publish a Pushmobile event whose Linkedid matches the channel's
        # linkedid (== chan.id for a fresh origination).
        call_id = 'test-call-id-caller-hangup'
        self.bus.publish(
            {
                'data': {
                    'UserEvent': 'Pushmobile',
                    'Uniqueid': call_id,
                    'Linkedid': chan.id,
                    'ChanVariable': {
                        'WAZO_USERUUID': 'eaa18a7f-3f49-419a-9abb-b445b8ba2e03',
                        'WAZO_TENANT_UUID': 'some-tenant-uuid',
                        'WAZO_SIP_CALL_ID': 'de9eb39fb7585796',
                        'XIVO_BASE_EXTEN': '8000',
                        'WAZO_DEREFERENCED_USERUUID': '',
                    },
                    'CallerIDName': 'Alice',
                    'CallerIDNum': '101',
                    'Event': 'UserEvent',
                    'WAZO_DST_UUID': 'fb27eb93-d21c-483f-8068-e685c90b07e1',
                    'WAZO_RING_TIME': '200',
                    'WAZO_VIDEO_ENABLED': '0',
                    'WAZO_TIMESTAMP': '2026-01-01T00:00:00.000+00:00',
                    'ConnectedLineName': '',
                    'ConnectedLineNum': '',
                    'Priority': '1',
                    'ChannelStateDesc': 'Ring',
                    'Language': 'en_US',
                    'Exten': 's',
                    'ChannelState': '4',
                    'Channel': 'PJSIP/test-0000001',
                    'Context': 'wazo-user-mobile-notification',
                    'Privilege': 'user,all',
                    'AccountCode': '',
                }
            },
            headers={'name': 'UserEvent'},
        )

        # Confirm send_push_notification was called (push notification sent).
        def push_notification_sent():
            assert_that(
                push_events.accumulate(),
                has_item(has_entries(name='call_push_notification')),
            )

        until.assert_(
            push_notification_sent,
            timeout=5,
            message='Push notification event never published',
        )

        # Caller hangs up before mobile registers — this is the bug scenario.
        chan.hangup()

        # The push notification must be cancelled.
        def push_notification_cancelled():
            assert_that(
                cancel_events.accumulate(),
                has_item(has_entries(name='call_cancel_push_notification')),
            )

        until.assert_(
            push_notification_cancelled,
            timeout=5,
            message='Push notification was not cancelled after caller hangup',
        )
