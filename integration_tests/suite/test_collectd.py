# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_item
from hamcrest import matches_regexp
from hamcrest import not_
from xivo_test_helpers import until

from .test_api.ari import MockChannel
from .test_api.base import IntegrationTest
from .test_api.constants import STASIS_APP_NAME
from .test_api.constants import STASIS_APP_INSTANCE_NAME
from .test_api.ctid_ng import new_call_id

ONE_HOUR = 3600


class TestCollectd(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCollectd, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_when_new_stasis_channel_then_stat_call_start(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/counter-start .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_then_stat_call_end(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/counter-end .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_then_stat_call_duration(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id,
                                            creation_time='2016-02-01T15:00:00.000-0500',
                                            timestamp='2016-02-01T16:00:00.000-0500')

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/gauge-duration .* N:3600'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_given_different_timezones_when_stasis_channel_destroyed_then_duration_is_correct(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id,
                                            creation_time='2016-02-01T15:00:00.000+0500',
                                            timestamp='2016-02-01T16:00:00.000-0500')

        def assert_function():
            expected_duration = 11 * ONE_HOUR
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/gauge-duration .* N:{duration}'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id,
                                                       duration=expected_duration)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_given_connected_when_stasis_channel_destroyed_then_do_not_stat_abandoned_call(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id,
                                            connected_number='another-number')

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/counter-abandoned .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id)
            assert_that(self.bus.events(), not_(has_item(matches_regexp(expected_message))))

        until.assert_(assert_function, tries=3)

    def test_given_not_connected_when_stasis_channel_destroyed_then_stat_abandoned_call(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id)
        self.stasis.event_channel_destroyed(channel_id=call_id)

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/counter-abandoned .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id)
            assert_that(self.bus.events(), has_item(matches_regexp(expected_message)))

        until.assert_(assert_function, tries=5)

    def test_when_connect_then_stat_connect(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='collectd.calls', exchange='collectd')

        self.stasis.event_stasis_start(channel_id=call_id, stasis_args=['dialed_from', 'another-channel'])

        def assert_function():
            expected_message = 'PUTVAL [^/]+/calls-{app}!{app_instance}!{call_id}/counter-connect .* N:1'
            expected_message = expected_message.format(app=STASIS_APP_NAME,
                                                       app_instance=STASIS_APP_INSTANCE_NAME,
                                                       call_id=call_id)
            assert_that(self.bus.events(), not_(has_item(matches_regexp(expected_message))))

        until.assert_(assert_function, tries=3)


class TestCollectdFirstStasisStart(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCollectdFirstStasisStart, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_when_new_stasis_channel_then_subscribe_to_all_channel_events(self):
        self.stasis.event_stasis_start(channel_id=new_call_id())

        def assert_function():
            assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
                'method': 'POST',
                'path': '/ari/applications/callcontrol/subscription',
                'query': [['eventSource', 'channel:']]
            }))))

        until.assert_(assert_function, tries=3)
