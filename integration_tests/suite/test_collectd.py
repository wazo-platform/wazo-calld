# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, has_item, matches_regexp, not_
from wazo_test_helpers import until

from .helpers.ari_ import MockChannel
from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id
from .helpers.constants import BUS_EXCHANGE_COLLECTD
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy

STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'switchboard-red'
COLLECTD_APP_START_EVENT = (
    f'PUTVAL [^/]+/calls-{STASIS_APP}.{STASIS_APP_INSTANCE}/counter-start .* N:1'
)
COLLECTD_APP_END_EVENT = (
    f'PUTVAL [^/]+/calls-{STASIS_APP}.{STASIS_APP_INSTANCE}/counter-end .* N:1'
)


class TestCollectd(IntegrationTest):
    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_when_new_channel_then_stat_channel_start(self):
        channel_id = 'channel-id'
        events = self.bus.accumulator(
            routing_key='collectd.channels', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.bus.send_ami_newchannel_event(channel_id=channel_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/channels-global/counter-created .* N:1'
            assert_that(events.accumulate(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_channel_ends_then_stat_channel_ended(self):
        channel_id = 'channel-id'
        events = self.bus.accumulator(
            routing_key='collectd.channels', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.bus.send_ami_hangup_event(channel_id=channel_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/channels-global/counter-ended .* N:1'
            assert_that(events.accumulate(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_new_stasis_channel_then_stat_call_start(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
        )

        def assert_function():
            assert_that(
                events.accumulate(),
                has_item(matches_regexp(COLLECTD_APP_START_EVENT)),
            )

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_then_stat_call_end(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
        )
        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
        )

        def assert_function():
            assert_that(
                events.accumulate(),
                has_item(matches_regexp(COLLECTD_APP_END_EVENT)),
            )

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_then_stat_call_duration(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
        )
        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            creation_time='2016-02-01T15:00:00.000-0500',
            timestamp='2016-02-01T16:00:00.000-0500',
        )

        def assert_function():
            expected_message = (
                'PUTVAL [^/]+/calls-{app}.{app_instance}/gauge-duration .* N:3600'
            )
            expected_message = expected_message.format(
                app=STASIS_APP, app_instance=STASIS_APP_INSTANCE
            )
            assert_that(events.accumulate(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_given_connected_when_stasis_channel_destroyed_then_do_not_stat_abandoned_call(
        self,
    ):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
            stasis_args=['dialed_from', 'another-channel'],
        )
        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            connected_number='another-number',
        )

        def assert_function():
            expected_message = (
                'PUTVAL [^/]+/calls-{app}.{app_instance}/counter-abandoned .* N:1'
            )
            expected_message = expected_message.format(
                app=STASIS_APP, app_instance=STASIS_APP_INSTANCE
            )
            assert_that(
                events.accumulate(), not_(has_item(matches_regexp(expected_message)))
            )

        until.assert_(assert_function, tries=3)

    def test_given_not_connected_when_stasis_channel_destroyed_then_stat_abandoned_call(
        self,
    ):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
        )
        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
        )

        def assert_function():
            expected_message = f'PUTVAL [^/]+/calls-{STASIS_APP}.{STASIS_APP_INSTANCE}/counter-abandoned .* N:1'
            assert_that(events.accumulate(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_connect_then_stat_connect(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )

        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
            stasis_args=['dialed_from', 'another-channel'],
        )

        def assert_function():
            message = f'PUTVAL [^/]+/calls-{STASIS_APP}.{STASIS_APP_INSTANCE}/counter-connect .* N:1'
            assert_that(events.accumulate(), not_(has_item(matches_regexp(message))))

        until.assert_(assert_function, tries=3)


class TestCollectdCalldRestart(IntegrationTest):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_calld_restarts_during_call_when_stasis_channel_destroyed_then_stat_call_end(
        self,
    ):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )
        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
        )

        def assert_call_has_been_handled_by_calld():
            assert_that(
                events.accumulate(),
                has_item(matches_regexp(COLLECTD_APP_START_EVENT)),
            )

        until.assert_(assert_call_has_been_handled_by_calld, tries=5)

        self.restart_service('calld')
        self.reset_clients()
        # wait for calld to reconnect to rabbitmq
        CalldEverythingOkWaitStrategy().wait(self)

        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
        )

        def assert_calld_sent_end_call_stat():
            assert_that(
                events.accumulate(),
                has_item(matches_regexp(COLLECTD_APP_END_EVENT)),
            )

        until.assert_(assert_calld_sent_end_call_stat, tries=5)


class TestCollectdRabbitMQRestart(IntegrationTest):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_rabbitmq_restarts_during_call_when_stasis_channel_destroyed_then_stat_call_end(
        self,
    ):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )
        self.stasis.event_stasis_start(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            stasis_app_instance=STASIS_APP_INSTANCE,
        )

        def assert_call_has_been_handled_by_calld():
            assert_that(
                events.accumulate(),
                has_item(matches_regexp(COLLECTD_APP_START_EVENT)),
            )

        until.assert_(assert_call_has_been_handled_by_calld, tries=5)

        self.restart_service('rabbitmq')
        # wait for calld to reconnect to rabbitmq
        CalldEverythingOkWaitStrategy().wait(self)
        self.reset_bus_client()
        self.reset_ari_bus()

        events = self.bus.accumulator(
            routing_key='collectd.calls', exchange=BUS_EXCHANGE_COLLECTD
        )
        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
        )

        def assert_calld_sent_end_call_stat():
            assert_that(
                events.accumulate(),
                has_item(matches_regexp(COLLECTD_APP_END_EVENT)),
            )

        until.assert_(assert_calld_sent_end_call_stat, tries=5)
