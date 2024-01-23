# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json

from hamcrest import assert_that, has_entries, has_entry, has_item, has_items, is_
from wazo_test_helpers import until

from .helpers.ari_ import MockChannel
from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id
from .helpers.confd import MockLine, MockUser
from .helpers.constants import (
    SOME_STASIS_APP,
    SOME_STASIS_APP_INSTANCE,
    VALID_TENANT,
    XIVO_UUID,
)
from .helpers.hamcrest_ import a_timestamp
from .helpers.wait_strategy import CalldConnectionsOkWaitStrategy

STASIS_APP = 'callcontrol'


class TestDialedFrom(IntegrationTest):
    asset = 'basic_rest'
    wait_strategy = CalldConnectionsOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_dialed_from_when_answer_then_the_two_are_talking(self):
        call_id = new_call_id()
        new_call_id_ = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id), MockChannel(id=new_call_id_))
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{call_id}': json.dumps(
                    {
                        'state': 'ringing',
                        'app': SOME_STASIS_APP,
                        'app_instance': SOME_STASIS_APP_INSTANCE,
                    }
                )
            }
        )

        self.stasis.event_answer_connect(
            from_=call_id,
            new_call_id=new_call_id_,
            stasis_app=SOME_STASIS_APP,
            stasis_app_instance=SOME_STASIS_APP_INSTANCE,
        )

        def assert_function():
            assert_that(
                self.ari.requests(),
                has_entry(
                    'requests',
                    has_items(
                        has_entries(
                            {
                                'method': 'POST',
                                'path': '/ari/channels/{channel_id}/answer'.format(
                                    channel_id=call_id
                                ),
                            }
                        ),
                        has_entries(
                            {
                                'method': 'POST',
                                'path': '/ari/channels/{channel_id}/answer'.format(
                                    channel_id=new_call_id_
                                ),
                            }
                        ),
                        has_entries(
                            {
                                'method': 'POST',
                                'path': '/ari/bridges/bridge-id/addChannel',
                                'query': [['channel', call_id]],
                            }
                        ),
                        has_entries(
                            {
                                'method': 'POST',
                                'path': '/ari/bridges/bridge-id/addChannel',
                                'query': [['channel', new_call_id_]],
                            }
                        ),
                        has_entries(
                            {
                                'method': 'POST',
                                'path': '/ari/bridges',
                                'query': [['type', 'mixing']],
                            }
                        ),
                    ),
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_given_dialed_from_when_originator_hangs_up_then_user_stops_ringing(self):
        call_id = 'call-id'
        new_call_id = 'new-call-id'
        self.ari.set_channels(
            MockChannel(id=call_id),
            MockChannel(
                id=new_call_id,
            ),
        )
        self.ari.set_channel_variable({new_call_id: {'WAZO_USERUUID': 'user-uuid'}})
        self.ari.set_global_variables(
            {
                f'XIVO_CHANNELS_{call_id}': json.dumps(
                    {'app': 'my-app', 'app_instance': 'sw1', 'state': 'ringing'}
                )
            }
        )
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='pjsip'))
        self.ari.set_originates(MockChannel(id=new_call_id))

        self.calld.connect_user(call_id, 'user-uuid')

        self.stasis.event_hangup(call_id)

        def assert_function():
            assert_that(
                self.ari.requests(),
                has_entry(
                    'requests',
                    has_items(
                        has_entries(
                            {
                                'method': 'DELETE',
                                'path': '/ari/channels/{call_id}'.format(
                                    call_id=new_call_id
                                ),
                            }
                        )
                    ),
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed(self):
        call_id = new_call_id()
        events = self.bus.accumulator(headers={'name': 'call_ended'})

        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            line_id=2,
            sip_call_id='foobar',
            creation_time='2016-02-01T15:00:00.000-05:00',
            answer_time='2022-03-08T04:09:00-05:00',
            cause=0,
            channel_direction='to-wazo',
        )

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_ended',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'creation_time': '2016-02-01T15:00:00.000-05:00',
                                        'sip_call_id': 'foobar',
                                        'line_id': 2,
                                        'reason_code': 0,
                                        'is_caller': True,
                                        'answer_time': is_(a_timestamp()),
                                        'hangup_time': is_(a_timestamp()),
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_ended',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_callee(self):
        call_id = new_call_id()
        events = self.bus.accumulator(headers={'name': 'call_ended'})

        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            line_id=2,
            sip_call_id='foobar',
            creation_time='2016-02-01T15:00:00.000-0500',
            cause=0,
            channel_direction='from-wazo',
        )

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_ended',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'creation_time': '2016-02-01T15:00:00.000-0500',
                                        'sip_call_id': 'foobar',
                                        'line_id': 2,
                                        'reason_code': 0,
                                        'is_caller': False,
                                        'hangup_time': is_(a_timestamp()),
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_ended',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_stasis_channel_destroyed_when_empty_values(self):
        call_id = new_call_id()
        events = self.bus.accumulator(headers={'name': 'call_ended'})

        self.stasis.event_channel_destroyed(
            channel_id=call_id,
            stasis_app=STASIS_APP,
            line_id='',
            sip_call_id='',
            creation_time='2016-02-01T15:00:00.000-0500',
        )

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_ended',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'creation_time': '2016-02-01T15:00:00.000-0500',
                                        'sip_call_id': '',
                                        'line_id': None,
                                        'hangup_time': is_(a_timestamp()),
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_ended',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)
