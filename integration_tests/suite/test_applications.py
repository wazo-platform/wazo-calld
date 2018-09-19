# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    contains,
    empty,
    has_entries,
    has_items,
    has_properties,
)
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.uuid_ import uuid_
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import MockApplication

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'


class BaseApplicationTestCase(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super(BaseApplicationTestCase, self).setUp()

        self.unknown_uuid = '00000000-0000-0000-0000-000000000000'

        self.node_app_uuid = 'f569ce99-45bf-46b9-a5db-946071dda71f'
        node_app = MockApplication(
            uuid=self.node_app_uuid,
            name='name',
            destination='node',
            type_='holding',
        )

        self.no_node_app_uuid = 'b00857f4-cb62-4773-adf7-ca870fa65c8d'
        no_node_app = MockApplication(
            uuid=self.no_node_app_uuid,
            name='name',
            destination=None,
        )
        self.confd.set_applications(node_app, no_node_app)

        # TODO: add a way to load new apps without restarting
        self._restart_ctid_ng()

    def call_app(self, app_uuid, variables=None):
        kwargs = {
            'endpoint': ENDPOINT_AUTOANSWER,
            'app': 'wazo-app-{}'.format(app_uuid),
            'appArgs': 'incoming',
            'variables': {
                'variables': {
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                },
            }
        }

        if variables:
            for key, value in variables.iteritems():
                kwargs['variables']['variables'][key] = value

        event_accumulator = self.bus.accumulator('applications.{uuid}.#'.format(uuid=app_uuid))
        channel = self.ari.channels.originate(**kwargs)
        for _ in xrange(10):
            events = event_accumulator.accumulate()
            for event in events:
                if event['name'] == 'application_call_entered':
                    return channel
        self.fail('Call start timedout')


class TestStasisTriggers(BaseApplicationTestCase):

    def test_entering_stasis_without_a_node(self):
        app_uuid = self.no_node_app_uuid
        event_accumulator = self.bus.accumulator('applications.{uuid}.#'.format(uuid=app_uuid))
        channel = self.call_app(app_uuid)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_call_entered',
                        data=has_entries(
                            application_uuid=app_uuid,
                            call=has_entries(
                                id=channel.id,
                                is_caller=True,
                                status='Up',
                                on_hold=False,
                                node_uuid=None,
                            )
                        )
                    )
                )
            )

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.get_application_calls(app_uuid)
        assert_that(response.json()['items'], has_items(has_entries(id=channel.id)))

    def test_entering_stasis_with_a_node(self):
        app_uuid = self.node_app_uuid
        event_accumulator = self.bus.accumulator('applications.{uuid}.#'.format(uuid=app_uuid))
        channel = self.call_app(app_uuid)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_call_entered',
                        data=has_entries(
                            call=has_entries(
                                id=channel.id,
                                is_caller=True,
                                status='Up',
                                on_hold=False,
                                node_uuid=None,
                            )
                        )
                    ),
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            application_uuid=app_uuid,
                            node=has_entries(
                                uuid=app_uuid,
                                calls=contains(has_entries(id=channel.id)),
                            )
                        )
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=app_uuid,
                            call=has_entries(
                                id=channel.id,
                                status='Up',
                                node_uuid=app_uuid,
                                is_caller=True,
                                on_hold=False,
                            )
                        )
                    )
                )
            )

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.get_application_calls(app_uuid)
        assert_that(response.json()['items'], has_items(has_entries(id=channel.id)))

        response = self.ctid_ng.get_application_node(app_uuid, app_uuid)
        assert_that(response.json()['calls'], has_items(has_entries(id=channel.id)))

    def test_event_destination_node_created(self):
        event_accumulator = self.bus.accumulator('applications.{uuid}.#'.format(uuid=self.node_app_uuid))
        self.reset_ari()
        self._restart_ctid_ng()

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_destination_node_created',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            node=has_entries(
                                uuid=self.node_app_uuid,
                                calls=empty(),
                            )
                        )
                    ),
                )
            )

        until.assert_(event_received, tries=3)

    def test_when_asterisk_restart_then_reconnect(self):
        event_accumulator = self.bus.accumulator('applications.{uuid}.#'.format(uuid=self.node_app_uuid))
        self.restart_service('ari')
        self.wait_strategy.wait(self)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(events, has_items(has_entries(name='application_destination_node_created')))

        until.assert_(event_received, tries=3)


class TestApplication(BaseApplicationTestCase):

    def test_get(self):
        response = self.ctid_ng.get_application(self.unknown_uuid)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        response = self.ctid_ng.get_application(self.node_app_uuid)
        assert_that(
            response.json(),
            has_entries(destination_node_uuid=self.node_app_uuid),
        )

        response = self.ctid_ng.get_application(self.no_node_app_uuid)
        assert_that(
            response.json(),
            has_entries(destination_node_uuid=None),
        )

        response = self.ctid_ng.get_application(self.node_app_uuid)
        assert_that(
            response.json(),
            has_entries(destination_node_uuid=self.node_app_uuid),
        )

    def test_delete_call(self):
        channel = self.call_app(self.node_app_uuid)
        routing_key = 'applications.{uuid}.calls.#'.format(uuid=self.node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        response = self.ctid_ng.delete_application_call(self.unknown_uuid, channel.id)
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.delete_application_call(self.no_node_app_uuid, channel.id)
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.delete_application_call(self.node_app_uuid, channel.id)
        assert_that(response, has_properties(status_code=204))

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                            )
                        ),
                    ),
                    has_entries(
                        name='application_call_deleted',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                            )
                        )
                    ),
                )
            )

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.delete_application_call(self.node_app_uuid, channel.id)
        assert_that(response, has_properties(status_code=404))

    def test_get_calls(self):
        response = self.ctid_ng.get_application_calls(self.unknown_uuid)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        response = self.ctid_ng.get_application_calls(self.no_node_app_uuid)
        assert_that(
            response.json(),
            has_entries(items=empty()),
        )

        channel = self.call_app(self.no_node_app_uuid, variables={'X_WAZO_FOO': 'bar'})
        response = self.ctid_ng.get_application_calls(self.no_node_app_uuid)
        assert_that(
            response.json(),
            has_entries(
                items=contains(
                    has_entries(
                        id=channel.id,
                        status='Up',
                        caller_id_name='Alice',
                        caller_id_number='555',
                        node_uuid=None,
                        on_hold=False,
                        is_caller=True,
                        variables={'FOO': 'bar'},
                    )
                )
            )
        )

    def test_post_call(self):
        context, exten = 'local', 'recipient_autoanswer'

        response = self.ctid_ng.application_new_call(self.unknown_uuid, context, exten)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        response = self.ctid_ng.application_new_call(self.no_node_app_uuid, context, 'not-found')
        assert_that(
            response,
            has_properties(status_code=400),
        )

        response = self.ctid_ng.application_new_call(self.no_node_app_uuid, 'not-found', exten)
        assert_that(
            response,
            has_properties(status_code=400),
        )

        routing_key = 'applications.{uuid}.#'.format(uuid=self.no_node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        call = self.ctid_ng.application_new_call(self.no_node_app_uuid, context, exten)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_call_initiated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            call=has_entries(
                                id=call.json()['id'],
                                is_caller=False,
                                status='Up',
                                on_hold=False,
                                node_uuid=None,
                            )
                        )
                    )
                )
            )

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.get_application_calls(self.no_node_app_uuid)
        assert_that(
            response.json(),
            has_entries(
                items=has_items(has_entries(id=call.json()['id'])),
            )
        )

    def test_post_node_call(self):
        context, exten = 'local', 'recipient_autoanswer'

        errors = [
            ((self.unknown_uuid, self.node_app_uuid, context, exten), 404),
            ((self.no_node_app_uuid, self.unknown_uuid, context, exten), 404),
            ((self.node_app_uuid, self.node_app_uuid, 'not-found', exten), 400),
            ((self.node_app_uuid, self.node_app_uuid, context, 'not-found'), 400),
        ]

        for args, status_code in errors:
            response = self.ctid_ng.application_new_node_call(*args)
            assert_that(
                response,
                has_properties(status_code=status_code),
                'failed with {}'.format(args)
            )

        routing_key = 'applications.{uuid}.#'.format(uuid=self.node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        call = self.ctid_ng.application_new_node_call(
            application_uuid=self.node_app_uuid,
            node_uuid=self.node_app_uuid,
            context=context,
            exten=exten,
        )

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_call_initiated',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            call=has_entries(
                                id=call.json()['id'],
                                is_caller=False,
                                status='Up',
                                on_hold=False,
                                node_uuid=None,
                            )
                        )
                    ),
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            node=has_entries(
                                uuid=self.node_app_uuid,
                                calls=contains(has_entries(id=call.json()['id']))
                            )
                        )
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            call=has_entries(
                                id=call.json()['id'],
                                node_uuid=self.node_app_uuid,
                            )
                        )
                    )
                )
            )

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.get_application_calls(self.node_app_uuid)
        assert_that(
            response.json(),
            has_entries(
                items=has_items(has_entries(id=call.json()['id'])),
            )
        )
        response = self.ctid_ng.get_application_node(self.node_app_uuid, self.node_app_uuid)
        assert_that(
            response.json(),
            has_entries(
                calls=has_items(has_entries(id=call.json()['id'])),
            )
        )

    def test_get_node(self):
        response = self.ctid_ng.get_application_node(self.unknown_uuid, self.unknown_uuid)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        response = self.ctid_ng.get_application_node(self.no_node_app_uuid, self.unknown_uuid)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        channel = self.call_app(self.node_app_uuid, variables={'X_WAZO_FOO': 'bar'})

        def call_entered_node():
            response = self.ctid_ng.get_application_node(self.node_app_uuid, self.node_app_uuid)
            assert_that(
                response.json(),
                has_entries(
                    uuid=self.node_app_uuid,
                    calls=contains(has_entries(id=channel.id)),
                )
            )

        until.assert_(call_entered_node, tries=3)

        channel.hangup()
        response = self.ctid_ng.get_application_node(self.node_app_uuid, self.node_app_uuid)
        assert_that(
            response.json(),
            has_entries(
                uuid=self.node_app_uuid,
                calls=empty(),
            ),
        )

    def test_get_nodes(self):
        response = self.ctid_ng.get_application_nodes(self.unknown_uuid)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        response = self.ctid_ng.get_application_nodes(self.no_node_app_uuid)
        assert_that(
            response.json(),
            has_entries(items=empty()),
        )

        response = self.ctid_ng.get_application_nodes(self.node_app_uuid)
        assert_that(
            response.json(),
            has_entries(items=contains(
                has_entries(uuid=self.node_app_uuid, calls=empty()),
            ))
        )

        # TODO: replace precondition with POST /applications/uuid/nodes/uuid/calls
        channel = self.call_app(self.node_app_uuid)

        def call_entered_node():
            response = self.ctid_ng.get_application_nodes(self.node_app_uuid)
            assert_that(
                response.json(),
                has_entries(items=contains(
                    has_entries(
                        uuid=self.node_app_uuid,
                        calls=contains(has_entries(id=channel.id)),
                    )
                ))
            )

        until.assert_(call_entered_node, tries=3)


class TestApplicationMoh(BaseApplicationTestCase):

    def test_put_moh_start(self):
        moh_uuid = '60f123e6-147b-487c-b08a-36395d43346e'  # From the confd mock
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)

        routing_key = 'applications.{uuid}.#'.format(uuid=self.no_node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        response = self.ctid_ng.application_call_moh_start(app_uuid, channel.id, moh_uuid)
        assert_that(response, has_properties(status_code=204))

        def music_on_hold_started_event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                                moh_uuid=moh_uuid,
                            )
                        )
                    )
                )
            )

        until.assert_(music_on_hold_started_event_received, tries=3)


class TestApplicationPlayback(BaseApplicationTestCase):

    def test_post_call_playback(self):
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(self.node_app_uuid)

        response = self.ctid_ng.application_call_playback(self.unknown_uuid, channel.id, body)
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_call_playback(self.node_app_uuid, self.unknown_uuid, body)
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_call_playback(self.no_node_app_uuid, channel.id, body)
        assert_that(response, has_properties(status_code=404))

        invalid_body = {'uri': 'unknown:foo'}
        response = self.ctid_ng.application_call_playback(self.node_app_uuid, channel.id, invalid_body)
        assert_that(response, has_properties(status_code=400))

        response = self.ctid_ng.application_call_playback(self.node_app_uuid, channel.id, body)
        assert_that(response, has_properties(status_code=200))
        assert_that(
            response.json(),
            has_entries(
                uuid=uuid_(),
                **body
            )
        )

    def test_delete(self):
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(self.node_app_uuid)
        playback = self.ctid_ng.application_call_playback(self.node_app_uuid, channel.id, body).json()

        response = self.ctid_ng.application_stop_playback(self.unknown_uuid, playback['uuid'])
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_stop_playback(self.node_app_uuid, self.unknown_uuid)
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_stop_playback(self.node_app_uuid, playback['uuid'])
        assert_that(response, has_properties(status_code=204))


class TestApplicationNode(BaseApplicationTestCase):

    def test_post_unknown_app(self):
        channel = self.call_app(self.no_node_app_uuid)

        response = self.ctid_ng.application_new_node(self.unknown_uuid, calls=[channel.id])
        assert_that(response, has_properties(status_code=404))

    def test_post_no_calls(self):
        response = self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[])
        assert_that(response, has_properties(status_code=400))

    def test_post_not_bridged(self):
        channel = self.call_app(self.no_node_app_uuid)
        routing_key = 'applications.{uuid}.#'.format(uuid=self.no_node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        response = self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel.id])
        assert_that(
            response.json(),
            has_entries(
                uuid=uuid_(),
                calls=contains(
                    has_entries(id=channel.id),
                )
            )
        )

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_node_created',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            node=has_entries(
                                uuid=response.json()['uuid'],
                                calls=empty(),
                            )
                        )
                    ),
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            node=has_entries(
                                uuid=response.json()['uuid'],
                                calls=contains(has_entries(id=channel.id)),
                            )
                        )
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                                caller_id_name='Alice',
                                caller_id_number='555',
                                is_caller=True,
                                node_uuid=response.json()['uuid'],
                                on_hold=False,
                                status='Up',
                            )
                        )
                    ),
                )
            )

        until.assert_(event_received, tries=3)

    def test_post_bridged(self):
        channel = self.call_app(self.no_node_app_uuid)
        self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel.id])

        response = self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel.id])
        assert_that(response, has_properties(status_code=400))

    def test_post_bridged_default_bridge(self):
        channel = self.call_app(self.node_app_uuid)

        routing_key = 'applications.{uuid}.#'.format(uuid=self.node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        response = self.ctid_ng.application_new_node(self.node_app_uuid, calls=[channel.id])
        assert_that(
            response.json(),
            has_entries(
                uuid=uuid_(),
                calls=contains(
                    has_entries(id=channel.id),
                )
            )
        )

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_node_created',
                        data=has_entries(
                            node=has_entries(uuid=response.json()['uuid']),
                        ),
                    ),
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            node=has_entries(uuid=self.node_app_uuid, calls=empty()),
                        )
                    ),
                    has_entries(
                        name='application_call_updated',
                    ),
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            node=has_entries(
                                uuid=response.json()['uuid'],
                                calls=contains(has_entries(id=channel.id)),
                            ),
                        ),
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            call=has_entries(
                                id=channel.id,
                                node_uuid=response.json()['uuid'],
                            )
                        ),
                    ),
                )
            )

        until.assert_(event_received, tries=3)

    def test_post_while_hanging_up(self):
        channel = self.call_app(self.node_app_uuid)
        channel_id = channel.id
        channel.hangup()

        response = self.ctid_ng.application_new_node(self.node_app_uuid, calls=[channel_id])
        assert_that(response, has_properties(status_code=400))

    def test_delete_unknown_app(self):
        channel = self.call_app(self.no_node_app_uuid)
        routing_key = 'applications.{uuid}.#'.format(uuid=self.no_node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)
        node = self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel.id]).json()

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(events, has_items(has_entries(name='application_node_created')))

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.delete_application_node(self.unknown_uuid, node['uuid'])
        assert_that(response, has_properties(status_code=404))

    def test_delete_destination_node(self):
        response = self.ctid_ng.delete_application_node(self.node_app_uuid, self.node_app_uuid)
        assert_that(response, has_properties(status_code=400))

    def test_delete(self):
        channel = self.call_app(self.no_node_app_uuid)
        routing_key = 'applications.{uuid}.#'.format(uuid=self.no_node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)
        node = self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel.id]).json()

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(events, has_items(has_entries(name='application_node_created')))

        until.assert_(event_received, tries=3)
        event_accumulator.reset()

        response = self.ctid_ng.delete_application_node(self.no_node_app_uuid, node['uuid'])
        assert_that(response, has_properties(status_code=204))

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            node=has_entries(
                                uuid=node['uuid'],
                                calls=empty(),
                            )
                        )
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                                caller_id_name='Alice',
                                caller_id_number='555',
                                status='Up',
                            )
                        )
                    ),
                    has_entries(
                        name='application_call_deleted',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                            )
                        )
                    ),
                    has_entries(
                        name='application_node_deleted',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            node=has_entries(
                                uuid=node['uuid'],
                                calls=empty(),
                            )
                        )
                    ),
                )
            )

        until.assert_(event_received, tries=3)


class TestApplicationNodeCall(BaseApplicationTestCase):

    def test_delete(self):
        channel = self.call_app(self.node_app_uuid)
        routing_key = 'applications.{uuid}.#'.format(uuid=self.node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        response = self.ctid_ng.delete_application_node_call(
            self.unknown_uuid,
            self.node_app_uuid,
            channel.id,
        )
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.delete_application_node_call(
            self.node_app_uuid,
            self.unknown_uuid,
            channel.id,
        )
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.delete_application_node_call(
            self.no_node_app_uuid,
            self.node_app_uuid,
            channel.id,
        )
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.delete_application_node_call(
            self.node_app_uuid,
            self.node_app_uuid,
            channel.id,
        )
        assert_that(response, has_properties(status_code=204))

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            node=has_entries(
                                uuid=self.node_app_uuid,
                                calls=empty(),
                            )
                        )
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.node_app_uuid,
                            call=has_entries(
                                id=channel.id,
                                caller_id_name='Alice',
                                caller_id_number='555',
                                status='Up',
                            )
                        )
                    ),
                )
            )

        until.assert_(event_received, tries=3)

        response = self.ctid_ng.delete_application_node_call(
            self.node_app_uuid,
            self.node_app_uuid,
            channel.id,
        )
        assert_that(response, has_properties(status_code=404))

        channel.hangup()

        response = self.ctid_ng.delete_application_node_call(
            self.node_app_uuid,
            self.node_app_uuid,
            channel.id,
        )
        assert_that(response, has_properties(status_code=404))

    def test_put(self):
        channel_1 = self.call_app(self.no_node_app_uuid)
        channel_2 = self.call_app(self.no_node_app_uuid)
        channel_3 = self.call_app(self.no_node_app_uuid)
        node_1 = self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel_1.id]).json()
        self.ctid_ng.application_new_node(self.no_node_app_uuid, calls=[channel_2.id]).json()

        response = self.ctid_ng.application_node_add_call(
            self.unknown_uuid,
            node_1['uuid'],
            channel_3.id,
        )
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_node_add_call(
            self.no_node_app_uuid,
            self.unknown_uuid,
            channel_3.id,
        )
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_node_add_call(
            self.node_app_uuid,
            node_1['uuid'],
            channel_3.id,
        )
        assert_that(response, has_properties(status_code=404))

        response = self.ctid_ng.application_node_add_call(
            self.no_node_app_uuid,
            node_1['uuid'],
            channel_2.id,
        )
        assert_that(response, has_properties(status_code=400))

        routing_key = 'applications.{uuid}.#'.format(uuid=self.no_node_app_uuid)
        event_accumulator = self.bus.accumulator(routing_key)

        response = self.ctid_ng.application_node_add_call(
            self.no_node_app_uuid,
            node_1['uuid'],
            channel_3.id,
        )
        assert_that(response, has_properties(status_code=204))

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                contains(
                    has_entries(
                        name='application_node_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            node=has_entries(
                                uuid=node_1['uuid'],
                                calls=contains(
                                    has_entries(id=channel_1.id),
                                    has_entries(id=channel_3.id),
                                )
                            )
                        ),
                    ),
                    has_entries(
                        name='application_call_updated',
                        data=has_entries(
                            application_uuid=self.no_node_app_uuid,
                            call=has_entries(
                                id=channel_3.id,
                            )
                        ),
                    ),
                )
            )

        until.assert_(event_received, tries=3)

        channel_3.hangup()

        response = self.ctid_ng.application_node_add_call(
            self.no_node_app_uuid,
            node_1['uuid'],
            channel_3.id,
        )
        assert_that(response, has_properties(status_code=404))
