# Copyright 2024-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import time
from uuid import uuid4

from ari.exceptions import ARINotFound
from hamcrest import assert_that, has_entries, has_item
from wazo_test_helpers import until

from .helpers.confd import MockLine, MockUser
from .helpers.constants import ENDPOINT_AUTOANSWER
from .helpers.real_asterisk import RealAsteriskIntegrationTest

_TEST_USER_UUID = 'eaa18a7f-3f49-419a-9abb-b445b8ba2e03'
_TEST_TENANT_UUID = 'some-tenant-uuid'


class TestDialMobile(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.confd.reset()

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

    def _start_dial_mobile_dial(self):
        """Originate a caller channel into dial_mobile dial mode and wait for Up."""
        chan = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app='dial_mobile',
            appArgs=['dial', 'nonexistent-aor'],
        )

        def channel_is_up():
            ch = self.ari.channels.get(channelId=chan.id)
            assert ch.json['state'] == 'Up'

        until.assert_(
            channel_is_up, timeout=5, message='Channel never reached Up state'
        )
        return chan

    def _publish_pushmobile(self, chan, call_id, ring_time='20'):
        self.bus.publish(
            {
                'data': {
                    'UserEvent': 'Pushmobile',
                    'Uniqueid': call_id,
                    'Linkedid': chan.id,
                    'ChanVariable': {
                        'WAZO_USERUUID': _TEST_USER_UUID,
                        'WAZO_TENANT_UUID': _TEST_TENANT_UUID,
                        'WAZO_SIP_CALL_ID': 'de9eb39fb7585796',
                        'XIVO_BASE_EXTEN': '8000',
                        'WAZO_DEREFERENCED_USERUUID': '',
                    },
                    'CallerIDName': 'Alice',
                    'CallerIDNum': '101',
                    'Event': 'UserEvent',
                    'WAZO_DST_UUID': _TEST_USER_UUID,
                    'WAZO_RING_TIME': ring_time,
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

    def _wait_push_notification(self, push_events):
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

    def _pstn_channels(self):
        return [
            c
            for c in self.ari.channels.list()
            if c.json['name'].startswith('Local/ring@local')
        ]

    def test_pstn_fallback_skipped_when_disabled(self):
        # Regression test: when the user has mobile_fallback_enabled=False,
        # the PSTN fallback must NOT originate a PSTN call when the timer fires.
        line_id = 424242
        self.confd.set_users(
            MockUser(
                uuid=_TEST_USER_UUID,
                line_ids=[line_id],
                mobile='ring',
                mobile_fallback_enabled=False,
                tenant_uuid=_TEST_TENANT_UUID,
            )
        )
        self.confd.set_lines(
            MockLine(id=line_id, context='local', tenant_uuid=_TEST_TENANT_UUID)
        )

        chan = self._start_dial_mobile_dial()
        push_events = self.bus.accumulator(headers={'name': 'call_push_notification'})
        self._publish_pushmobile(chan, f'test-pstn-disabled-{uuid4()}', ring_time='20')
        self._wait_push_notification(push_events)

        # PSTN timer fires at max(10, 0.5 * 20) = 10 s. Wait beyond that and
        # verify no PSTN channel was ever originated.
        time.sleep(12)
        assert (
            self._pstn_channels() == []
        ), 'PSTN fallback originated a call despite mobile_fallback_enabled=False'

        chan.hangup()

    def test_caller_hangup_cancels_active_pstn_fallback(self):
        # Regression test: once the PSTN fallback has fired and a PSTN channel
        # is ringing, hanging up the caller must also hang up the PSTN channel.
        line_id = 424242
        self.confd.set_users(
            MockUser(
                uuid=_TEST_USER_UUID,
                line_ids=[line_id],
                mobile='ring',
                mobile_fallback_enabled=True,
                tenant_uuid=_TEST_TENANT_UUID,
            )
        )
        self.confd.set_lines(
            MockLine(id=line_id, context='local', tenant_uuid=_TEST_TENANT_UUID)
        )

        chan = self._start_dial_mobile_dial()
        push_events = self.bus.accumulator(headers={'name': 'call_push_notification'})
        self._publish_pushmobile(chan, f'test-pstn-hangup-{uuid4()}', ring_time='20')
        self._wait_push_notification(push_events)

        # PSTN timer fires at max(10, 0.5 * 20) = 10 s. Wait until the
        # Local/ring@local PSTN leg is originated.
        pstn_channel = until.true(
            lambda: next(iter(self._pstn_channels()), None),
            timeout=15,
            message='PSTN fallback channel was never originated',
        )

        # Caller hangs up after the PSTN has been originated.
        chan.hangup()

        def pstn_channel_gone():
            try:
                self.ari.channels.get(channelId=pstn_channel.id)
                return False
            except ARINotFound:
                return True

        until.true(
            pstn_channel_gone,
            timeout=5,
            message='PSTN fallback channel was not hung up after caller hangup',
        )

    def test_pstn_fallback_preserves_push_when_confd_unavailable(self):
        line_id = 424242
        self.confd.set_users(
            MockUser(
                uuid=_TEST_USER_UUID,
                line_ids=[line_id],
                mobile='ring',
                mobile_fallback_enabled=True,
                tenant_uuid=_TEST_TENANT_UUID,
            )
        )
        self.confd.set_lines(
            MockLine(id=line_id, context='local', tenant_uuid=_TEST_TENANT_UUID)
        )

        chan = self._start_dial_mobile_dial()
        push_events = self.bus.accumulator(headers={'name': 'call_push_notification'})
        cancel_events = self.bus.accumulator(
            headers={'name': 'call_cancel_push_notification'}
        )
        self._publish_pushmobile(
            chan, f'test-pstn-confd-down-{uuid4()}', ring_time='20'
        )
        self._wait_push_notification(push_events)

        # PSTN timer fires at max(10, 0.5 * 20) = 10 s. Bring confd down
        # before then and wait past the timer window.
        with self.confd_stopped():
            time.sleep(12)
            assert cancel_events.accumulate() == [], (
                'cancel_push_notification was published despite confd being '
                'unavailable; the push should remain active when the fallback '
                'cannot dispatch a PSTN leg'
            )
            assert (
                self._pstn_channels() == []
            ), 'PSTN leg was originated despite confd being unavailable'

        chan.hangup()

    def test_pstn_fallback_cancels_push_after_dispatch(self):
        line_id = 424242
        self.confd.set_users(
            MockUser(
                uuid=_TEST_USER_UUID,
                line_ids=[line_id],
                mobile='ring',
                mobile_fallback_enabled=True,
                tenant_uuid=_TEST_TENANT_UUID,
            )
        )
        self.confd.set_lines(
            MockLine(id=line_id, context='local', tenant_uuid=_TEST_TENANT_UUID)
        )

        chan = self._start_dial_mobile_dial()
        push_events = self.bus.accumulator(headers={'name': 'call_push_notification'})
        cancel_events = self.bus.accumulator(
            headers={'name': 'call_cancel_push_notification'}
        )
        self._publish_pushmobile(
            chan, f'test-pstn-cancels-push-{uuid4()}', ring_time='20'
        )
        self._wait_push_notification(push_events)

        # Wait for the PSTN leg to be originated first.
        until.true(
            lambda: next(iter(self._pstn_channels()), None),
            timeout=15,
            message='PSTN fallback channel was never originated',
        )

        # Cancel-push must have been published as part of the successful
        # PSTN dispatch.
        def push_notification_cancelled():
            assert_that(
                cancel_events.accumulate(),
                has_item(has_entries(name='call_cancel_push_notification')),
            )

        until.assert_(
            push_notification_cancelled,
            timeout=5,
            message='Push notification was not cancelled after PSTN dispatch',
        )

        chan.hangup()

    def test_cancel_push_via_dial_end_uses_linkedid(self):
        # Regression test for the linkedid-keyed state invariant: the bus
        # consumer's DialEnd handler looks up push state by event['Linkedid'].
        # Internal state is now keyed by Linkedid too, so the lookup must
        # succeed even when the Pushmobile event's Uniqueid differs from its
        # Linkedid (the common production case, where Pushmobile is emitted
        # from a Local;2 leg of a Dial).
        chan = self._start_dial_mobile_dial()
        push_events = self.bus.accumulator(headers={'name': 'call_push_notification'})
        cancel_events = self.bus.accumulator(
            headers={'name': 'call_cancel_push_notification'}
        )

        push_uniqueid = f'test-push-uniqueid-{uuid4()}'
        # _publish_pushmobile sets Uniqueid=push_uniqueid, Linkedid=chan.id —
        # deliberately distinct values.
        self._publish_pushmobile(chan, push_uniqueid, ring_time='200')
        self._wait_push_notification(push_events)

        # Fake a DialEnd for the wazo_wait_for_registration dial that didn't
        # answer. The bus consumer only reads DestContext, DialStatus, and
        # Linkedid; the rest of the payload is padding to satisfy AMI
        # deserialization.
        self.bus.publish(
            {
                'data': {
                    'Event': 'DialEnd',
                    'DialStatus': 'NOANSWER',
                    'DestContext': 'wazo_wait_for_registration',
                    'Linkedid': chan.id,
                    'Uniqueid': chan.id,
                    'Channel': 'PJSIP/test-00000001',
                    'DestChannel': ('Local/test@wazo_wait_for_registration-00000001;1'),
                    'DestLinkedid': chan.id,
                    'DestUniqueid': 'fake-dest-uniqueid',
                    'CallerIDNum': '101',
                    'CallerIDName': 'Alice',
                    'ConnectedLineNum': '<unknown>',
                    'ConnectedLineName': '<unknown>',
                    'Context': 'user',
                    'Exten': 's',
                    'Priority': '1',
                    'Language': 'en_US',
                    'DestExten': 's',
                    'DestPriority': '1',
                    'DestLanguage': 'en_US',
                    'DestCallerIDNum': 's',
                    'DestCallerIDName': '<unknown>',
                    'DestConnectedLineNum': '<unknown>',
                    'DestConnectedLineName': '<unknown>',
                    'ChannelState': '6',
                    'ChannelStateDesc': 'Up',
                    'DestChannelState': '5',
                    'DestChannelStateDesc': 'Ringing',
                    'ChanVariable': {},
                    'DestChanVariable': {},
                    'AccountCode': '',
                    'DestAccountCode': '',
                    'Privilege': 'call,all',
                }
            },
            headers={'name': 'DialEnd'},
        )

        # The cancel-push event must be published — proving the linkedid-keyed
        # lookup succeeded despite the Pushmobile's Uniqueid being different.
        def push_notification_cancelled():
            assert_that(
                cancel_events.accumulate(),
                has_item(has_entries(name='call_cancel_push_notification')),
            )

        until.assert_(
            push_notification_cancelled,
            timeout=5,
            message=(
                'cancel_push_notification was not published despite DialEnd '
                'carrying the matching Linkedid'
            ),
        )

        chan.hangup()
