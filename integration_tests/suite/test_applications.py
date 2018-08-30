# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    contains,
    empty,
    has_entries,
    has_properties,
)
from xivo_test_helpers import until
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import MockApplication

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'


class BaseApplicationsTestCase(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super(BaseApplicationsTestCase, self).setUp()

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
                    'WAZO_APP_UUID': app_uuid,
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                },
            }
        }

        if variables:
            for key, value in variables.iteritems():
                kwargs['variables']['variables'][key] = value

        return self.ari.channels.originate(**kwargs)


class TestStatisIncoming(BaseApplicationsTestCase):

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
                            )
                        )
                    )
                )
            )

        until.assert_(event_received, tries=3)

        # TODO check that the call is in the stasis application

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
                            )
                        )
                    ),
                    has_entries(
                        name='application_destination_node_created',
                        data=has_entries(
                            application_uuid=app_uuid,
                            node=has_entries(
                                uuid=app_uuid,
                                calls=empty(),
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
                                # FIXME: where are the is_caller and on_hold fields???
                                # is_caller=True,
                                # on_hold=False,
                            )
                        )
                    )
                )
            )

        until.assert_(event_received, tries=3)

        # TODO: assert that the call is bridged


class TestApplications(BaseApplicationsTestCase):

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

        with self.confd_stopped():
            response = self.ctid_ng.get_application(self.node_app_uuid)

        assert_that(
            response,
            has_properties(status_code=503),
        )
