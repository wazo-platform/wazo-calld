# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    contains,
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


class TestStatisIncoming(BaseApplicationsTestCase):

    def test_entering_stasis_without_a_node(self):
        app_uuid = 'b00857f4-cb62-4773-adf7-ca870fa65c8d'
        app = MockApplication(
            uuid=app_uuid,
            name='name',
            destination=None,
        )
        self.confd.set_applications(app)
        event_accumulator = self.bus.accumulator('applications.{uuid}.#'.format(uuid=app_uuid))

        # TODO: add a way to load new apps without restarting
        self._restart_ctid_ng()

        channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            app='wazo-app-{}'.format(app_uuid),
            appArgs='incoming',
            variables={
                'variables': {
                    'WAZO_APP_UUID': app_uuid,
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                },
            }
        )

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


class TestApplications(BaseApplicationsTestCase):

    def test_get(self):
        unknown_uuid = '00000000-0000-0000-0000-000000000000'
        response = self.ctid_ng.get_application(unknown_uuid)
        assert_that(
            response,
            has_properties(status_code=404),
        )

        app_uuid_with_destination_node = 'b00857f4-cb62-4773-adf7-ca870fa65c8d'
        app_with_node = MockApplication(
            uuid=app_uuid_with_destination_node,
            name='name',
            destination='node',
        )
        app_uuid_without_destination_node = '25707f7d-d429-4366-a3d1-92a7c6b20353'
        app_without_node = MockApplication(
            uuid=app_uuid_without_destination_node,
            name='name',
        )
        self.confd.set_applications(app_with_node, app_without_node)

        response = self.ctid_ng.get_application(app_uuid_with_destination_node)
        assert_that(
            response.json(),
            has_entries(destination_node_uuid=app_uuid_with_destination_node),
        )

        response = self.ctid_ng.get_application(app_uuid_without_destination_node)
        assert_that(
            response.json(),
            has_entries(destination_node_uuid=None),
        )

        with self.confd_stopped():
            response = self.ctid_ng.get_application(app_uuid_with_destination_node)
        assert_that(
            response,
            has_properties(status_code=503),
        )
