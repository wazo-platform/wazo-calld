# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    has_entries,
    has_properties,
)
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import MockApplication


class BaseApplicationsTestCase(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super(BaseApplicationsTestCase, self).setUp()


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
