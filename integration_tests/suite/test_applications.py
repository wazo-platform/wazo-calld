# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ari.exceptions import ARIServerError
from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    contains_inanyorder,
    empty,
    equal_to,
    has_entries,
    has_entry,
    has_item,
    has_items,
    has_length,
    has_properties,
    not_,
)
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises
from wazo_test_helpers.hamcrest.uuid_ import uuid_

from .helpers.confd import MockApplication, MockMoh, MockUser
from .helpers.constants import ENDPOINT_AUTOANSWER, VALID_TENANT
from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy, NoWaitStrategy


class BaseApplicationTestCase(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        super().setUp()

        self.unknown_uuid = '00000000-0000-0000-0000-000000000000'

        self.node_app_uuid = 'f569ce99-45bf-46b9-a5db-946071dda71f'
        node_app = MockApplication(
            uuid=self.node_app_uuid,
            tenant_uuid=VALID_TENANT,
            name='name',
            destination='node',
            type_='holding',
            answer=False,
        )

        self.no_node_app_uuid = 'b00857f4-cb62-4773-adf7-ca870fa65c8d'
        no_node_app = MockApplication(
            uuid=self.no_node_app_uuid,
            tenant_uuid=VALID_TENANT,
            name='name',
            destination=None,
        )
        self.confd.set_applications(node_app, no_node_app)

        self.moh_uuid = '60f123e6-147b-487c-b08a-36395d43346e'
        moh = MockMoh(self.moh_uuid)
        self.confd.set_moh(moh)

        # TODO: add a way to load new apps without restarting
        self._restart_calld()
        CalldEverythingOkWaitStrategy().wait(self)

        def applications_created():
            try:
                app1 = self.calld_client.applications.get(self.node_app_uuid)
                app2 = self.calld_client.applications.get(self.no_node_app_uuid)
            except CalldError:
                app1 = None
                app2 = None
            assert_that(app1, not_(None))
            assert_that(app2, not_(None))

        until.assert_(applications_created, tries=5)

    def app_event_accumulator(self, app_uuid):
        return self.bus.accumulator(
            headers={
                'application_uuid': app_uuid,
            }
        )

    def call_app(self, app_uuid, variables=None):
        kwargs: dict = {
            'endpoint': ENDPOINT_AUTOANSWER,
            'app': f'wazo-app-{app_uuid}',
            'appArgs': 'incoming',
            'variables': {
                'variables': {
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                },
            },
        }

        if variables:
            for key, value in variables.items():
                kwargs['variables']['variables'][key] = value

        event_accumulator = self.app_event_accumulator(app_uuid)

        channel = self.ari.channels.originate(**kwargs)

        def call_entered_application(event_accumulator):
            events = event_accumulator.accumulate()
            for event in events:
                if event['name'] == 'application_call_entered':
                    return channel

        return until.true(
            call_entered_application,
            event_accumulator,
            timeout=10,
            message='Failed to start call',
        )

    def call_app_incoming(self, app_uuid):
        event_accumulator = self.app_event_accumulator(app_uuid)

        self.docker_exec(
            ['asterisk', '-rx', f'test new {app_uuid} applications'],
            'ari',
        )

        def call_entered_application(event_accumulator):
            events = event_accumulator.accumulate()
            for event in events:
                if event['name'] == 'application_call_entered':
                    return self.ari.channels.get(channelId=event['data']['call']['id'])

        return until.true(
            call_entered_application,
            event_accumulator,
            timeout=10,
            message='Failed to start call',
        )

    def call_from_user(self, app_uuid, exten):
        context = f'stasis-wazo-app-{app_uuid}'
        response = self.chan_test.call(context, exten)
        return response.json()['uniqueid']


class TestStasisTriggers(BaseApplicationTestCase):
    def test_entering_stasis_user_outgoing_call(self):
        app_uuid = self.no_node_app_uuid
        event_accumulator = self.app_event_accumulator(app_uuid)
        exten = '1001'
        channel_id = self.call_from_user(app_uuid, exten)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            name='application_user_outgoing_call_created',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    dialed_extension=exten,
                                    id=channel_id,
                                    is_caller=True,
                                    status='Ring',
                                    on_hold=False,
                                    node_uuid=None,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(app_uuid)['items']
        assert_that(calls, has_items(has_entries(id=channel_id)))

    def test_entering_stasis_without_a_node(self):
        app_uuid = self.no_node_app_uuid
        event_accumulator = self.app_event_accumulator(app_uuid)
        channel = self.call_app(app_uuid)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            name='application_call_entered',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    is_caller=True,
                                    status='Up',
                                    on_hold=False,
                                    node_uuid=None,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(app_uuid)['items']
        assert_that(calls, has_items(has_entries(id=channel.id)))

    def test_entering_stasis_with_a_node(self):
        app_uuid = self.node_app_uuid
        event_accumulator = self.app_event_accumulator(app_uuid)
        channel = self.call_app(app_uuid)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_entered',
                            data=has_entries(
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    is_caller=True,
                                    status='Up',
                                    on_hold=False,
                                    node_uuid=None,
                                )
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                node=has_entries(
                                    uuid=app_uuid,
                                    calls=contains_exactly(has_entries(id=channel.id)),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    status='Up',
                                    node_uuid=app_uuid,
                                    is_caller=True,
                                    on_hold=False,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(app_uuid)['items']
        assert_that(calls, has_items(has_entries(id=channel.id)))

        node = self.calld_client.applications.get_node(app_uuid, app_uuid)
        assert_that(node['calls'], has_items(has_entries(id=channel.id)))

    def test_event_destination_node_created(self):
        with self._calld_stopped():
            self.reset_ari()
            event_accumulator = self.app_event_accumulator(self.node_app_uuid)
        CalldEverythingOkWaitStrategy().wait(self)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            name='application_destination_node_created',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                node=has_entries(
                                    uuid=self.node_app_uuid,
                                    calls=empty(),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

    def test_when_asterisk_restart_then_reconnect(self):
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)
        self.restart_service('ari')
        CalldEverythingOkWaitStrategy().wait(self)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            name='application_destination_node_created'
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

    def test_confd_application_event_then_ari_client_is_reset(self):
        app_uuid = '00000000-0000-0000-0000-000000000001'
        event_accumulator = self.bus.accumulator(
            headers={'name': 'application_destination_node_created'}
        )

        self.bus.send_application_created_event(app_uuid, destination='node')

        def event_received():  # type: ignore
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entry(
                            'name', 'application_destination_node_created'
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

        event_accumulator = self.bus.accumulator(
            headers={
                'name': 'application_call_entered',
                'application_uuid': self.no_node_app_uuid,
            }
        )

        self.call_app(self.no_node_app_uuid)

        def event_received():  # type: ignore
            events = event_accumulator.accumulate()
            assert_that(events, has_length(1))

        until.assert_(event_received, tries=5)

    def test_confd_application_created_event_then_stasis_reconnect(self):
        app_uuid = '00000000-0000-0000-0000-000000000001'
        event_accumulator = self.bus.accumulator(
            headers={
                'name': 'application_destination_node_created',
            }
        )

        self.bus.send_application_created_event(app_uuid, destination='node')

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            name='application_destination_node_created'
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

    def test_confd_application_edited_event_then_destination_node_created(self):
        event_accumulator = self.bus.accumulator(
            headers={
                'name': 'application_destination_node_created',
            }
        )

        self.bus.send_application_edited_event(
            self.no_node_app_uuid, destination='node'
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            name='application_destination_node_created'
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

    def test_confd_application_edited_event_then_destination_node_deleted(self):
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        self.bus.send_application_edited_event(self.node_app_uuid, destination=None)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(name='application_node_deleted'),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=3)

    def test_confd_application_deleted_event_then_application_deleted(self):
        # self.ari.bridges.destroy(bridgeId=self.node_app_uuid)
        # event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)

        self.bus.send_application_deleted_event(self.no_node_app_uuid)

        application_name = f'wazo-app-{self.no_node_app_uuid}'

        def application_deleted():
            try:
                app_names = [app['name'] for app in self.ari.applications.list()]
            except ARIServerError:
                assert False, 'Failed to list ARI applications'

            assert (
                application_name not in app_names
            ), 'Stasis application has not been deleted'

        until.assert_(application_deleted, tries=3)


class TestApplication(BaseApplicationTestCase):
    def test_get(self):
        assert_that(
            calling(self.calld_client.applications.get).with_args(self.unknown_uuid),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        application = self.calld_client.applications.get(self.node_app_uuid)
        assert_that(
            application,
            has_entries(destination_node_uuid=self.node_app_uuid),
        )

        application = self.calld_client.applications.get(self.no_node_app_uuid)
        assert_that(
            application,
            has_entries(destination_node_uuid=None),
        )

    def test_confd_application_created_event_update_cache(self):
        app_uuid = '00000000-0000-0000-0000-000000000001'
        self.bus.send_application_created_event(app_uuid)

        def application_created():
            try:
                application = self.calld_client.applications.get(app_uuid)
            except CalldError:
                application = None
            assert_that(application, has_entries(destination_node_uuid=None))

        until.assert_(application_created, tries=5)

    def test_confd_application_edited_event_update_cache(self):
        self.bus.send_application_edited_event(
            self.no_node_app_uuid, destination='node'
        )

        def application_updated():
            try:
                application = self.calld_client.applications.get(self.no_node_app_uuid)
            except CalldError:
                application = None
            assert_that(application, has_entries(destination_node_uuid=uuid_()))

        until.assert_(application_updated, tries=5)

    def test_confd_application_deleted_event_update_cache(self):
        self.bus.send_application_deleted_event(self.no_node_app_uuid)

        def application_deleted():
            assert_that(
                calling(self.calld_client.applications.get).with_args(
                    self.no_node_app_uuid
                ),
                raises(CalldError).matching(has_properties(status_code=404)),
            )

        until.assert_(application_deleted, tries=5)

    def test_given_no_confd_when_node_app_then_return_503(self):
        with self.confd_stopped():
            self._restart_calld()
            assert_that(
                calling(self.calld_client.applications.get).with_args(
                    self.node_app_uuid
                ),
                raises(CalldError).matching(has_properties(status_code=503)),
            )

    def test_delete_call(self):
        channel = self.call_app(self.node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.hangup_call).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.hangup_call).with_args(
                self.no_node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        self.calld_client.applications.hangup_call(self.node_app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_deleted',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=10)

        assert_that(
            calling(self.calld_client.applications.hangup_call).with_args(
                self.node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_get_calls(self):
        assert_that(
            calling(self.calld_client.applications.list_calls).with_args(
                self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        calls = self.calld_client.applications.list_calls(self.no_node_app_uuid)[
            'items'
        ]
        assert_that(calls, empty())

        channel = self.call_app(self.no_node_app_uuid, variables={'X_WAZO_FOO': 'bar'})
        calls = self.calld_client.applications.list_calls(self.no_node_app_uuid)[
            'items'
        ]
        assert_that(
            calls,
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    status='Up',
                    caller_id_name='Alice',
                    caller_id_number='555',
                    node_uuid=None,
                    on_hold=False,
                    is_caller=True,
                    muted=False,
                    variables={'FOO': 'bar'},
                )
            ),
        )

    def test_post_call(self):
        context, exten = 'local', 'recipient_autoanswer'

        assert_that(
            calling(self.calld_client.applications.make_call).with_args(
                self.unknown_uuid, {'context': context, 'exten': exten}
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.make_call).with_args(
                self.no_node_app_uuid, {'context': context, 'exten': 'not-found'}
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )
        assert_that(
            calling(self.calld_client.applications.make_call).with_args(
                self.no_node_app_uuid, {'context': 'not-found', 'exten': exten}
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

        event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)

        call_args = {
            'context': context,
            'exten': exten,
            'displayed_caller_id_name': 'Foo Bar',
            'displayed_caller_id_number': '5555555555',
            'variables': {'X_WAZO_FOO': 'BAR'},
        }
        call = self.calld_client.applications.make_call(
            self.no_node_app_uuid, call_args
        )

        channel = self.ari.channels.get(channelId=call['id']).json
        assert_that(
            channel,
            has_entries(connected=has_entries(name='Foo Bar', number='5555555555')),
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_initiated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    is_caller=False,
                                    status='Up',
                                    on_hold=False,
                                    muted=False,
                                    node_uuid=None,
                                    variables={'FOO': 'BAR'},
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(self.no_node_app_uuid)[
            'items'
        ]
        assert_that(
            calls,
            has_items(
                has_entries(
                    id=call['id'],
                    variables={'FOO': 'BAR'},
                ),
            ),
        )

    def test_post_call_extension_containing_whitespace(self):
        context, exten = 'local', 'rec ipi\rent_\nauto\tanswer'
        event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)

        call_args = {
            'context': context,
            'exten': exten,
            'displayed_caller_id_name': 'Foo Bar',
            'displayed_caller_id_number': '5555555555',
            'variables': {'X_WAZO_FOO': 'BAR'},
        }
        call = self.calld_client.applications.make_call(
            self.no_node_app_uuid, call_args
        )

        channel = self.ari.channels.get(channelId=call['id']).json
        assert_that(
            channel,
            has_entries(connected=has_entries(name='Foo Bar', number='5555555555')),
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_initiated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    is_caller=False,
                                    status='Up',
                                    on_hold=False,
                                    muted=False,
                                    node_uuid=None,
                                    variables={'FOO': 'BAR'},
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(self.no_node_app_uuid)[
            'items'
        ]
        assert_that(
            calls,
            has_items(
                has_entries(
                    id=call['id'],
                    variables={'FOO': 'BAR'},
                ),
            ),
        )

    def test_post_node_call(self):
        context, exten = 'local', 'recipient_autoanswer'

        errors = [
            (
                (
                    self.unknown_uuid,
                    self.node_app_uuid,
                    {'context': context, 'exten': exten},
                ),
                404,
            ),
            (
                (
                    self.no_node_app_uuid,
                    self.unknown_uuid,
                    {'context': context, 'exten': exten},
                ),
                404,
            ),
            (
                (
                    self.node_app_uuid,
                    self.node_app_uuid,
                    {'context': 'not-found', 'exten': exten},
                ),
                400,
            ),
            (
                (
                    self.node_app_uuid,
                    self.node_app_uuid,
                    {'context': context, 'exten': 'not-found'},
                ),
                400,
            ),
        ]

        for args, status_code in errors:
            assert_that(
                calling(self.calld_client.applications.make_call_to_node).with_args(
                    *args
                ),
                raises(CalldError).matching(has_properties(status_code=status_code)),
            )

        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        call_args = {
            'context': context,
            'exten': exten,
            'displayed_caller_id_name': 'Foo Bar',
            'displayed_caller_id_number': '1234',
            'variables': {'X_WAZO_FOO': 'BAR'},
        }
        call = self.calld_client.applications.make_call_to_node(
            self.node_app_uuid,
            self.node_app_uuid,
            call_args,
        )

        assert_that(call, has_entries(variables={'FOO': 'BAR'}))

        channel = self.ari.channels.get(channelId=call['id']).json
        assert_that(
            channel, has_entries(connected=has_entries(name='Foo Bar', number='1234'))
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_initiated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    is_caller=False,
                                    status='Up',
                                    on_hold=False,
                                    node_uuid=None,
                                    variables={'FOO': 'BAR'},
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                node=has_entries(
                                    uuid=self.node_app_uuid,
                                    calls=contains_exactly(has_entries(id=call['id'])),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    node_uuid=self.node_app_uuid,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(self.node_app_uuid)['items']
        assert_that(calls, has_items(has_entries(id=call['id'])))

        node = self.calld_client.applications.get_node(
            self.node_app_uuid, self.node_app_uuid
        )
        assert_that(node, has_entries(calls=has_items(has_entries(id=call['id']))))

    def test_post_node_call_extension_containing_whitespace(self):
        context, exten = 'local', 'rec ipi\rent_\nauto\tanswer'
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        call_args = {
            'context': context,
            'exten': exten,
            'displayed_caller_id_name': 'Foo Bar',
            'displayed_caller_id_number': '1234',
            'variables': {'X_WAZO_FOO': 'BAR'},
        }
        call = self.calld_client.applications.make_call_to_node(
            self.node_app_uuid,
            self.node_app_uuid,
            call_args,
        )

        assert_that(call, has_entries(variables={'FOO': 'BAR'}))

        channel = self.ari.channels.get(channelId=call['id']).json
        assert_that(
            channel, has_entries(connected=has_entries(name='Foo Bar', number='1234'))
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_initiated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    is_caller=False,
                                    status='Up',
                                    on_hold=False,
                                    node_uuid=None,
                                    variables={'FOO': 'BAR'},
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                node=has_entries(
                                    uuid=self.node_app_uuid,
                                    calls=contains_exactly(has_entries(id=call['id'])),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    node_uuid=self.node_app_uuid,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(self.node_app_uuid)['items']
        assert_that(calls, has_items(has_entries(id=call['id'])))

        node = self.calld_client.applications.get_node(
            self.node_app_uuid, self.node_app_uuid
        )
        assert_that(node, has_entries(calls=has_items(has_entries(id=call['id']))))

    def test_post_node_call_user(self):
        user_uuid = 'joiner-uuid'
        user_uuid_with_no_lines = '3d696b59-bc6a-4f89-a5b4-ce06f09a64cb'
        self.confd.set_users(
            MockUser(uuid=user_uuid, line_ids=['some-line-id']),
            MockUser(uuid=user_uuid_with_no_lines, line_ids=[]),
        )

        errors = [
            ((self.unknown_uuid, self.node_app_uuid, {'user_uuid': user_uuid}), 404),
            ((self.no_node_app_uuid, self.unknown_uuid, {'user_uuid': user_uuid}), 404),
            (
                (
                    self.node_app_uuid,
                    self.node_app_uuid,
                    {'user_uuid': self.unknown_uuid},
                ),
                400,
            ),
            (
                (
                    self.node_app_uuid,
                    self.node_app_uuid,
                    {'user_uuid': user_uuid_with_no_lines},
                ),
                400,
            ),
        ]

        for args, status_code in errors:
            assert_that(
                calling(
                    self.calld_client.applications.make_call_user_to_node
                ).with_args(*args),
                raises(CalldError).matching(has_properties(status_code=status_code)),
            )

        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        call_args = {
            'user_uuid': user_uuid,
            'displayed_caller_id_name': 'Foo Bar',
            'displayed_caller_id_number': '1234',
            'variables': {'X_WAZO_FOO': 'BAR'},
        }
        call = self.calld_client.applications.make_call_user_to_node(
            application_uuid=self.node_app_uuid,
            node_uuid=self.node_app_uuid,
            call=call_args,
        )

        assert_that(call, has_entries(variables={'FOO': 'BAR'}))

        channel = self.ari.channels.get(channelId=call['id']).json
        assert_that(
            channel, has_entries(connected=has_entries(name='Foo Bar', number='1234'))
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_initiated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    is_caller=False,
                                    status='Up',
                                    on_hold=False,
                                    node_uuid=None,
                                    variables={'FOO': 'BAR'},
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                node=has_entries(
                                    uuid=self.node_app_uuid,
                                    calls=contains_exactly(has_entries(id=call['id'])),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=call['id'],
                                    node_uuid=self.node_app_uuid,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

        calls = self.calld_client.applications.list_calls(self.node_app_uuid)['items']
        assert_that(
            calls,
            has_items(has_entries(id=call['id'])),
        )
        node = self.calld_client.applications.get_node(
            self.node_app_uuid, self.node_app_uuid
        )
        assert_that(node, has_entries(calls=has_items(has_entries(id=call['id']))))

    def test_get_node(self):
        assert_that(
            calling(self.calld_client.applications.get_node).with_args(
                self.unknown_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.get_node).with_args(
                self.no_node_app_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        node = self.calld_client.applications.get_node(
            self.node_app_uuid, self.node_app_uuid
        )
        assert_that(node, has_entries(uuid=self.node_app_uuid, calls=empty()))

    def test_get_nodes(self):
        assert_that(
            calling(self.calld_client.applications.list_nodes).with_args(
                self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        nodes = self.calld_client.applications.list_nodes(self.no_node_app_uuid)[
            'items'
        ]
        assert_that(nodes, empty())

        nodes = self.calld_client.applications.list_nodes(self.node_app_uuid)['items']
        assert_that(
            nodes, contains_exactly(has_entries(uuid=self.node_app_uuid, calls=empty()))
        )

        # TODO: replace precondition with POST /applications/uuid/nodes/uuid/calls
        channel = self.call_app(self.node_app_uuid)

        def call_entered_node():
            nodes = self.calld_client.applications.list_nodes(self.node_app_uuid)[
                'items'
            ]
            assert_that(
                nodes,
                contains_exactly(
                    has_entries(
                        uuid=self.node_app_uuid,
                        calls=contains_exactly(has_entries(id=channel.id)),
                    )
                ),
            )

        until.assert_(call_entered_node, tries=5)


class TestApplicationMute(BaseApplicationTestCase):
    def test_put_mute_start(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        other_channel = self.call_app(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.start_mute).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.start_mute).with_args(
                app_uuid, other_channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.start_mute(app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                contains_exactly(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    muted=True,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        assert_that(
            self.calld_client.applications.list_calls(app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    muted=True,
                )
            ),
        )

    def test_put_mute_stop(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        other_channel = self.call_app(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.stop_mute).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.stop_mute).with_args(
                app_uuid, other_channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.stop_mute(app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    muted=False,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        assert_that(
            self.calld_client.applications.list_calls(app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    muted=False,
                )
            ),
        )


class TestApplicationHold(BaseApplicationTestCase):
    def test_put_hold_start(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        other_channel = self.call_app(self.node_app_uuid)
        event_accumulator = self.app_event_accumulator(app_uuid)

        assert_that(
            calling(self.calld_client.applications.start_hold).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        assert_that(
            calling(self.calld_client.applications.start_hold).with_args(
                app_uuid, other_channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        self.calld_client.applications.start_hold(app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    on_hold=True,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        assert_that(
            self.calld_client.applications.list_calls(app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    on_hold=True,
                )
            ),
        )

    def test_put_hold_stop(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        other_channel = self.call_app(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.stop_hold).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        assert_that(
            calling(self.calld_client.applications.stop_hold).with_args(
                app_uuid, other_channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        self.calld_client.applications.start_hold(app_uuid, channel.id)

        def call_held():
            calls = self.calld_client.applications.list_calls(app_uuid)['items']
            for call in calls:
                if call['id'] != channel.id:
                    continue
                return call['on_hold']
            return False

        until.true(call_held)

        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.stop_hold(app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    on_hold=False,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        assert_that(
            self.calld_client.applications.list_calls(app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    on_hold=False,
                )
            ),
        )


class TestApplicationSnoop(BaseApplicationTestCase):
    def setUp(self):
        super().setUp()
        self.app_uuid = self.no_node_app_uuid
        self.caller_channel = self.call_app(self.no_node_app_uuid)
        node = self.calld_client.applications.create_node(
            self.app_uuid,
            [self.caller_channel.id],
        )
        self.answering_channel = self.calld_client.applications.make_call_to_node(
            self.app_uuid,
            node['uuid'],
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

    def test_snoop_created_event(self):
        supervisor_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

        event_accumulator = self.app_event_accumulator(self.app_uuid)

        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }
        snoop = self.calld_client.applications.snoops(
            self.app_uuid, self.caller_channel.id, snoop_args
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_snoop_created',
                            data=has_entries(
                                application_uuid=self.app_uuid,
                                snoop=has_entries(
                                    uuid=snoop['uuid'],
                                    snooped_call_id=self.caller_channel.id,
                                    snooping_call_id=supervisor_channel['id'],
                                    whisper_mode=snoop_args['whisper_mode'],
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

    def test_snoop_deleted_event(self):
        supervisor_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }
        snoop = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_args,
        )

        event_accumulator = self.app_event_accumulator(self.app_uuid)

        self.calld_client.applications.delete_snoop(self.app_uuid, snoop['uuid'])

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_snoop_deleted',
                            data=has_entries(
                                application_uuid=self.app_uuid,
                                snoop=has_entries(uuid=snoop['uuid']),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

    def test_snoop_updated_event(self):
        supervisor_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }
        snoop = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_args,
        )

        event_accumulator = self.app_event_accumulator(self.app_uuid)

        snoop_args = {'whisper_mode': 'in'}
        self.calld_client.applications.update_snoop(
            self.app_uuid,
            snoop['uuid'],
            snoop_args,
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_snoop_updated',
                            data=has_entries(
                                application_uuid=self.app_uuid,
                                snoop=has_entries(
                                    uuid=snoop['uuid'],
                                    snooped_call_id=self.caller_channel.id,
                                    snooping_call_id=supervisor_channel['id'],
                                    whisper_mode=snoop_args['whisper_mode'],
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

    def test_list(self):
        snoop = self.calld_client.applications.list_snoops(self.app_uuid)
        assert_that(snoop, has_entries(items=empty()))

        assert_that(
            calling(self.calld_client.applications.list_snoops).with_args(
                self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        supervisor_1_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )
        supervisor_2_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

        snoop_1_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_1_channel['id'],
        }
        snoop_1 = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_1_args,
        )

        snoop_2_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_2_channel['id'],
        }
        snoop_2 = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_2_args,
        )

        # Test snoop being created (snoop bridge with no channels) does not cause errors
        self.ari.bridges.create(name=f'wazo-app-snoop-{self.app_uuid}')

        snoops = self.calld_client.applications.list_snoops(self.app_uuid)
        assert_that(
            snoops,
            has_entries(
                items=contains_inanyorder(
                    snoop_1,
                    snoop_2,
                )
            ),
        )

    def test_get(self):
        supervisor_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )
        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }
        snoop = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_args,
        )

        snoop = self.calld_client.applications.get_snoop(self.app_uuid, snoop['uuid'])
        assert_that(snoop, equal_to(snoop))

        assert_that(
            calling(self.calld_client.applications.get_snoop).with_args(
                self.unknown_uuid, snoop['uuid']
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        assert_that(
            calling(self.calld_client.applications.get_snoop).with_args(
                self.app_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_post_snoop(self):
        unrelated_channel = self.call_app(self.node_app_uuid)
        supervisor_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )
        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }

        assert_that(
            calling(self.calld_client.applications.snoops).with_args(
                self.unknown_uuid,
                self.caller_channel.id,
                snoop_args,
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.snoops).with_args(
                self.app_uuid,
                unrelated_channel.id,
                snoop_args,
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        snoop_unrelated_args = {
            'whisper_mode': 'both',
            'snooping_call_id': unrelated_channel.id,
        }
        assert_that(
            calling(self.calld_client.applications.snoops).with_args(
                self.app_uuid,
                self.caller_channel.id,
                snoop_unrelated_args,
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

        invalid_whisper_mode = [
            'foobar',
            'In',
            False,
            True,
            None,
            42,
            [],
            {},
        ]
        for whisper_mode in invalid_whisper_mode:
            snoop_args = {
                'whisper_mode': whisper_mode,
                'snooping_call_id': supervisor_channel['id'],
            }
            assert_that(
                calling(self.calld_client.applications.snoops).with_args(
                    self.app_uuid, self.caller_channel.id, snoop_args
                ),
                raises(CalldError).matching(has_properties(status_code=400)),
            )

        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }
        snoop = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_args,
        )

        assert_that(
            snoop,
            has_entries(
                uuid=uuid_(),
                whisper_mode='both',
                snooped_call_id=self.caller_channel.id,
                snooping_call_id=supervisor_channel['id'],
            ),
        )

        calls = self.calld_client.applications.list_calls(self.app_uuid)['items']
        snoop_uuid = snoop['uuid']
        assert_that(
            calls,
            has_items(
                has_entries(
                    id=self.caller_channel.id,
                    snoops=has_entries(
                        {
                            snoop_uuid: has_entries(
                                uuid=snoop_uuid,
                                role='snooped',
                            )
                        }
                    ),
                ),
                has_entries(
                    id=supervisor_channel['id'],
                    snoops=has_entries(
                        {
                            snoop_uuid: has_entries(
                                uuid=snoop_uuid,
                                role='snooper',
                            )
                        }
                    ),
                ),
            ),
        )

    def test_put(self):
        supervisor_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

        snoop_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_channel['id'],
        }
        snoop = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_args,
        )

        assert_that(
            calling(self.calld_client.applications.update_snoop).with_args(
                self.unknown_uuid,
                snoop['uuid'],
                snoop_args,
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        assert_that(
            calling(self.calld_client.applications.update_snoop).with_args(
                self.app_uuid,
                self.unknown_uuid,
                snoop_args,
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        invalid_whisper_mode = [
            'foobar',
            'In',
            False,
            True,
            None,
            42,
            [],
            {},
        ]
        for whisper_mode in invalid_whisper_mode:
            snoop_args = {'whisper_mode': whisper_mode}
            assert_that(
                calling(self.calld_client.applications.update_snoop).with_args(
                    self.app_uuid,
                    snoop['uuid'],
                    snoop_args,
                ),
                raises(CalldError).matching(has_properties(status_code=400)),
            )

    def test_delete(self):
        supervisor_1_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )
        supervisor_2_channel = self.calld_client.applications.make_call(
            self.app_uuid,
            {'context': 'local', 'exten': 'recipient_autoanswer'},
        )

        snoop_1_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_1_channel['id'],
        }
        snoop_1 = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_1_args,
        )

        snoop_2_args = {
            'whisper_mode': 'both',
            'snooping_call_id': supervisor_2_channel['id'],
        }
        snoop_2 = self.calld_client.applications.snoops(
            self.app_uuid,
            self.caller_channel.id,
            snoop_2_args,
        )

        self.calld_client.applications.delete_snoop(self.app_uuid, snoop_2['uuid'])
        assert_that(
            self.calld_client.applications.list_snoops(self.app_uuid),
            has_entries(items=contains_inanyorder(snoop_1)),
        )

        assert_that(
            calling(self.calld_client.applications.delete_snoop).with_args(
                self.app_uuid,
                snoop_2['uuid'],
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        assert_that(
            calling(self.calld_client.applications.delete_snoop).with_args(
                self.unknown_uuid,
                snoop_2['uuid'],
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )


class TestApplicationMoh(BaseApplicationTestCase):
    def test_put_moh_start_fail(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        unrelated_channel = self.call_app(self.node_app_uuid)

        params = [
            (self.unknown_uuid, channel.id, self.moh_uuid),
            (app_uuid, unrelated_channel.id, self.moh_uuid),
            (app_uuid, channel.id, self.unknown_uuid),
        ]

        for param in params:
            assert_that(
                calling(self.calld_client.applications.start_moh).with_args(*param),
                raises(CalldError).matching(has_properties(status_code=404)),
            )

    def test_put_moh_stop_fail(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        unrelated_channel = self.call_app(self.node_app_uuid)
        self.calld_client.applications.start_moh(app_uuid, channel.id, self.moh_uuid)

        params = [
            (self.unknown_uuid, channel.id),
            (app_uuid, unrelated_channel.id),
        ]

        for param in params:
            assert_that(
                calling(self.calld_client.applications.stop_moh).with_args(*param),
                raises(CalldError).matching(has_properties(status_code=404)),
            )

    def test_put_moh_start_success(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)

        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.start_moh(app_uuid, channel.id, self.moh_uuid)

        def music_on_hold_started_event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    moh_uuid=self.moh_uuid,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(music_on_hold_started_event_received, tries=5)

        assert_that(
            self.calld_client.applications.list_calls(app_uuid)['items'],
            contains_exactly(has_entries(id=channel.id, moh_uuid=self.moh_uuid)),
        )

    def test_put_moh_stop_success(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.start_moh(app_uuid, channel.id, self.moh_uuid)
        self.calld_client.applications.stop_moh(app_uuid, channel.id)

        def call_updated_event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    moh_uuid=self.moh_uuid,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    moh_uuid=None,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(call_updated_event_received, tries=5)

        assert_that(
            self.calld_client.applications.list_calls(app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    moh_uuid=None,
                )
            ),
        )

    def test_confd_moh_created_event_update_cache(self):
        moh_uuid = '00000000-0000-0000-0000-000000000001'
        self.confd.set_moh()
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        self._hitting_moh_cache(app_uuid, channel.id)
        self.bus.send_moh_created_event(moh_uuid)
        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.start_moh(app_uuid, channel.id, moh_uuid)

        def music_on_hold_started_event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events, contains_exactly(has_entries(name='application_call_updated'))
            )

        until.assert_(music_on_hold_started_event_received, tries=10)

        calls = self.calld_client.applications.list_calls(app_uuid)['items']
        assert_that(
            calls,
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    moh_uuid=moh_uuid,
                )
            ),
        )

    def test_confd_moh_deleted_event_update_cache(self):
        app_uuid = self.no_node_app_uuid
        channel = self.call_app(self.no_node_app_uuid)
        self._hitting_moh_cache(app_uuid, channel.id)
        self.bus.send_moh_deleted_event(self.moh_uuid)

        assert_that(
            calling(self.calld_client.applications.start_moh).with_args(
                app_uuid, channel.id, self.moh_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def _hitting_moh_cache(self, app_uuid, channel_id):
        random = '00000000-0000-0000-0000-000000000000'
        try:
            self.calld_client.applications.start_moh(app_uuid, channel_id, random)
        except CalldError:
            pass


class TestApplicationPlayback(BaseApplicationTestCase):
    def test_post_call_playback(self):
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.send_playback).with_args(
                self.unknown_uuid, channel.id, body
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.send_playback).with_args(
                self.node_app_uuid, self.unknown_uuid, body
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.send_playback).with_args(
                self.no_node_app_uuid, channel.id, body
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        invalid_body = {'uri': 'unknown:foo'}
        assert_that(
            calling(self.calld_client.applications.send_playback).with_args(
                self.node_app_uuid, channel.id, invalid_body
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

        playback = self.calld_client.applications.send_playback(
            self.node_app_uuid, channel.id, body
        )
        assert_that(playback, has_entries(uuid=uuid_(), **body))

    def test_playback_created_event(self):
        app_uuid = self.node_app_uuid
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(app_uuid)
        event_accumulator = self.app_event_accumulator(app_uuid)

        playback = self.calld_client.applications.send_playback(
            app_uuid, channel.id, body
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_playback_created',
                            data=has_entries(
                                application_uuid=app_uuid,
                                playback=has_entries(
                                    uuid=playback['uuid'],
                                    language='en',
                                    uri='sound:tt-weasels',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

    def test_delete(self):
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(self.node_app_uuid)
        playback = self.calld_client.applications.send_playback(
            self.node_app_uuid, channel.id, body
        )

        assert_that(
            calling(self.calld_client.applications.delete_playback).with_args(
                self.unknown_uuid, playback['uuid']
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.delete_playback).with_args(
                self.node_app_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        self.calld_client.applications.delete_playback(
            self.node_app_uuid, playback['uuid']
        )

    def test_playback_deleted_event(self):
        app_uuid = self.node_app_uuid
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(app_uuid)

        playback = self.calld_client.applications.send_playback(
            app_uuid, channel.id, body
        )

        event_accumulator = self.app_event_accumulator(app_uuid)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_playback_deleted',
                            data=has_entries(
                                application_uuid=app_uuid,
                                playback=has_entries(
                                    uuid=playback['uuid'],
                                    language='en',
                                    uri='sound:tt-weasels',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=50)

    def test_playback_deleted_event_on_stop(self):
        app_uuid = self.node_app_uuid
        body = {'uri': 'sound:tt-weasels'}
        channel = self.call_app(app_uuid)

        playback = self.calld_client.applications.send_playback(
            app_uuid, channel.id, body
        )

        event_accumulator = self.app_event_accumulator(app_uuid)

        self.calld_client.applications.delete_playback(app_uuid, playback['uuid'])

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_playback_deleted',
                            data=has_entries(
                                application_uuid=app_uuid,
                                playback=has_entries(
                                    uuid=playback['uuid'],
                                    language='en',
                                    uri='sound:tt-weasels',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)


class TestApplicationAnswer(BaseApplicationTestCase):
    def test_answer_call(self):
        channel = self.call_app_incoming(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.answer_call).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.answer_call).with_args(
                self.node_app_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.answer_call).with_args(
                self.no_node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        self.calld_client.applications.answer_call(self.node_app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_answered',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    status='Up',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, timeout=3)

        assert_that(
            self.calld_client.applications.list_calls(self.node_app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    status='Up',
                )
            ),
        )


class TestApplicationProgress(BaseApplicationTestCase):
    def test_progress_start(self):
        channel = self.call_app_incoming(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.start_progress).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.start_progress).with_args(
                self.node_app_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.start_progress).with_args(
                self.no_node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        self.calld_client.applications.start_progress(self.node_app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_progress_started',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    status='Progress',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, timeout=3)

        assert_that(
            self.calld_client.applications.list_calls(self.node_app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    status='Progress',
                )
            ),
        )

    def test_progress_stop(self):
        channel = self.call_app_incoming(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.stop_progress).with_args(
                self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.stop_progress).with_args(
                self.node_app_uuid, self.unknown_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.stop_progress).with_args(
                self.no_node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        self.calld_client.applications.stop_progress(self.node_app_uuid, channel.id)

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_progress_stopped',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    status='Ring',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, timeout=3)

        assert_that(
            self.calld_client.applications.list_calls(self.node_app_uuid)['items'],
            contains_exactly(
                has_entries(
                    id=channel.id,
                    conversation_id=channel.id,
                    status='Ring',
                )
            ),
        )


class TestApplicationNode(BaseApplicationTestCase):
    def test_post_unknown_app(self):
        channel = self.call_app(self.no_node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.create_node).with_args(
                self.unknown_uuid, [channel.id]
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_post_no_calls(self):
        assert_that(
            calling(self.calld_client.applications.create_node).with_args(
                self.no_node_app_uuid, []
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

    def test_post_not_bridged(self):
        channel = self.call_app(self.no_node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)

        node = self.calld_client.applications.create_node(
            self.no_node_app_uuid, [channel.id]
        )
        assert_that(
            node,
            has_entries(
                uuid=uuid_(),
                calls=contains_exactly(
                    has_entries(id=channel.id),
                ),
            ),
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_node_created',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                node=has_entries(
                                    uuid=node['uuid'],
                                    calls=empty(),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                node=has_entries(
                                    uuid=node['uuid'],
                                    calls=contains_exactly(has_entries(id=channel.id)),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    caller_id_name='Alice',
                                    caller_id_number='555',
                                    is_caller=True,
                                    node_uuid=node['uuid'],
                                    on_hold=False,
                                    status='Up',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

    def test_post_bridged(self):
        channel = self.call_app(self.no_node_app_uuid)
        self.calld_client.applications.create_node(self.no_node_app_uuid, [channel.id])

        assert_that(
            calling(self.calld_client.applications.create_node).with_args(
                self.no_node_app_uuid, [channel.id]
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

    def test_post_bridged_default_bridge(self):
        channel = self.call_app(self.node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        node = self.calld_client.applications.create_node(
            self.node_app_uuid, [channel.id]
        )
        assert_that(
            node,
            has_entries(
                uuid=uuid_(),
                calls=contains_exactly(
                    has_entries(id=channel.id),
                ),
            ),
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_node_created',
                            data=has_entries(
                                node=has_entries(uuid=node['uuid']),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                node=has_entries(
                                    uuid=self.node_app_uuid, calls=empty()
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                node=has_entries(
                                    uuid=node['uuid'],
                                    calls=contains_exactly(has_entries(id=channel.id)),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    node_uuid=node['uuid'],
                                )
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

    def test_post_while_hanging_up(self):
        channel = self.call_app(self.node_app_uuid)
        channel_id = channel.id
        channel.hangup()

        assert_that(
            calling(self.calld_client.applications.create_node).with_args(
                self.node_app_uuid, [channel_id]
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

    def test_delete_unknown_app(self):
        channel = self.call_app(self.no_node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)
        node = self.calld_client.applications.create_node(
            self.no_node_app_uuid, [channel.id]
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(name='application_node_created'),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)

        assert_that(
            calling(self.calld_client.applications.delete_node).with_args(
                self.unknown_uuid, node['uuid']
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_delete_destination_node(self):
        assert_that(
            calling(self.calld_client.applications.delete_node).with_args(
                self.node_app_uuid, self.node_app_uuid
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

    def test_delete(self):
        channel = self.call_app(self.no_node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)
        node = self.calld_client.applications.create_node(
            self.no_node_app_uuid, [channel.id]
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(name='application_node_created'),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)
        event_accumulator.reset()

        self.calld_client.applications.delete_node(self.no_node_app_uuid, node['uuid'])

        def event_received():  # type: ignore
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                node=has_entries(
                                    uuid=node['uuid'],
                                    calls=empty(),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    caller_id_name='Alice',
                                    caller_id_number='555',
                                    status='Up',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_deleted',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_node_deleted',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                node=has_entries(
                                    uuid=node['uuid'],
                                    calls=empty(),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)


class TestApplicationNodeCall(BaseApplicationTestCase):
    def test_delete(self):
        channel = self.call_app(self.node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        assert_that(
            calling(self.calld_client.applications.delete_call_from_node).with_args(
                self.unknown_uuid, self.node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.delete_call_from_node).with_args(
                self.node_app_uuid, self.unknown_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.delete_call_from_node).with_args(
                self.no_node_app_uuid, self.node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        self.calld_client.applications.delete_call_from_node(
            self.node_app_uuid,
            self.node_app_uuid,
            channel.id,
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                node=has_entries(
                                    uuid=self.node_app_uuid,
                                    calls=empty(),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call=has_entries(
                                    id=channel.id,
                                    conversation_id=channel.id,
                                    caller_id_name='Alice',
                                    caller_id_number='555',
                                    status='Up',
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

        assert_that(
            calling(self.calld_client.applications.delete_call_from_node).with_args(
                self.node_app_uuid, self.node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        channel.hangup()

        assert_that(
            calling(self.calld_client.applications.delete_call_from_node).with_args(
                self.node_app_uuid, self.node_app_uuid, channel.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_put(self):
        channel_1 = self.call_app(self.no_node_app_uuid)
        channel_2 = self.call_app(self.no_node_app_uuid)
        channel_3 = self.call_app(self.no_node_app_uuid)
        node_1 = self.calld_client.applications.create_node(
            self.no_node_app_uuid, [channel_1.id]
        )
        self.calld_client.applications.create_node(
            self.no_node_app_uuid, [channel_2.id]
        )

        assert_that(
            calling(self.calld_client.applications.join_node).with_args(
                self.unknown_uuid, node_1['uuid'], channel_3.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.join_node).with_args(
                self.no_node_app_uuid, self.unknown_uuid, channel_3.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.applications.join_node).with_args(
                self.node_app_uuid, node_1['uuid'], channel_3.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        assert_that(
            calling(self.calld_client.applications.join_node).with_args(
                self.no_node_app_uuid,
                node_1['uuid'],
                channel_2.id,
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

        event_accumulator = self.app_event_accumulator(self.no_node_app_uuid)

        self.calld_client.applications.join_node(
            self.no_node_app_uuid,
            node_1['uuid'],
            channel_3.id,
        )

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_node_updated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                node=has_entries(
                                    uuid=node_1['uuid'],
                                    calls=contains_exactly(
                                        has_entries(id=channel_1.id),
                                        has_entries(id=channel_3.id),
                                    ),
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                    has_entries(
                        message=has_entries(
                            name='application_call_updated',
                            data=has_entries(
                                application_uuid=self.no_node_app_uuid,
                                call=has_entries(
                                    id=channel_3.id,
                                ),
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    ),
                ),
            )

        until.assert_(event_received, tries=5)

        channel_3.hangup()

        assert_that(
            calling(self.calld_client.applications.join_node).with_args(
                self.no_node_app_uuid, node_1['uuid'], channel_3.id
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_node_conversation_id(self):
        calls = self.calld_client.applications.list_calls(self.no_node_app_uuid)[
            'items'
        ]
        assert_that(calls, empty())

        channel1 = self.call_app(self.node_app_uuid)
        channel2 = self.call_app(self.node_app_uuid)
        channel3 = self.call_app(self.node_app_uuid)
        self.calld_client.applications.create_node(
            self.node_app_uuid, [channel1.id, channel2.id, channel3.id]
        )

        calls = self.calld_client.applications.list_calls(self.node_app_uuid)['items']
        assert_that(
            calls,
            has_items(
                has_entries(id=channel1.id, conversation_id=channel1.id),
                has_entries(id=channel2.id, conversation_id=channel1.id),
                has_entries(id=channel3.id, conversation_id=channel1.id),
            ),
        )


class TestDTMFEvents(BaseApplicationTestCase):
    def test_that_events_are_received(self):
        channel = self.call_app(self.node_app_uuid)
        event_accumulator = self.app_event_accumulator(self.node_app_uuid)

        self.chan_test.send_dtmf(channel.id, '1')

        def event_received():
            events = event_accumulator.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            name='application_call_dtmf_received',
                            data=has_entries(
                                application_uuid=self.node_app_uuid,
                                call_id=channel.id,
                                dtmf='1',
                            ),
                        ),
                        headers=has_entry('tenant_uuid', VALID_TENANT),
                    )
                ),
            )

        until.assert_(event_received, tries=5)


class TestApplicationSendDTMF(BaseApplicationTestCase):
    def test_put_dtmf(self):
        app_uuid = self.node_app_uuid
        channel = self.call_app(app_uuid)

        # Unknown channel ID
        assert_that(
            calling(self.calld_client.applications.send_dtmf_digits).with_args(
                app_uuid, self.unknown_uuid, '1234'
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Unknown app UUID
        assert_that(
            calling(self.calld_client.applications.send_dtmf_digits).with_args(
                self.unknown_uuid, channel.id, '5678'
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # Invalid DTMF
        assert_that(
            calling(self.calld_client.applications.send_dtmf_digits).with_args(
                app_uuid, channel.id, 'invalid'
            ),
            raises(CalldError).matching(has_properties(status_code=400)),
        )

        event_accumulator = self.bus.accumulator(
            headers={
                'name': 'DTMFEnd',
            }
        )

        # Valid DTMF
        test_str = '12*#'
        self.calld_client.applications.send_dtmf_digits(app_uuid, channel.id, test_str)

        def amid_dtmf_events_received():
            events = event_accumulator.accumulate()
            for expected_digit in test_str:
                assert_that(
                    events,
                    has_item(
                        has_entries(
                            name='DTMFEnd',
                            data=has_entries(
                                Direction='Received',
                                Digit=expected_digit,
                                Uniqueid=channel.id,
                            ),
                        )
                    ),
                )

        until.assert_(amid_dtmf_events_received, tries=5)
