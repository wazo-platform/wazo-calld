# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, contains_exactly, equal_to, has_entries
from wazo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.confd import MockLine, MockTrunk
from .helpers.constants import VALID_TENANT, VALID_TOKEN
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


class TestListEndpoints(IntegrationTest):
    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.ari.reset()
        self.confd.reset()
        # Start from an empty cache, filled only by the lines and trunks below
        self.restart_service('calld')
        self.reset_clients()
        self.wait_strategy.wait(self)

    def test_list_lines_paginated(self):
        names = ['line-b', 'line-c', 'line-a']
        lines = [
            MockLine(
                line_id,
                name=name,
                protocol='sip',
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', name]],
                },
                tenant_uuid=VALID_TENANT,
            )
            for line_id, name in enumerate(names, start=1)
        ]
        self.confd.set_lines(*lines)
        for line_id, name in enumerate(names, start=1):
            self.bus.send_line_endpoint_sip_associated_event(
                VALID_TENANT, line_id, endpoint_id=line_id, endpoint_name=name
            )
        until.assert_(self._assert_lines_total, len(names), timeout=5)

        response = self.calld.get_lines_result(
            token=VALID_TOKEN,
            tenant_uuid=VALID_TENANT,
            limit=2,
            offset=1,
        )

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.json(),
            has_entries(
                items=contains_exactly(
                    has_entries(name='line-b'), has_entries(name='line-c')
                ),
                total=3,
                filtered=3,
            ),
        )

        response = self.calld.get_lines_result(
            token=VALID_TOKEN,
            tenant_uuid=VALID_TENANT,
            order='id',
            direction='desc',
            limit=1,
        )

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.json(),
            has_entries(items=contains_exactly(has_entries(id=3, name='line-a'))),
        )

    def test_list_lines_invalid_params(self):
        for params in ({'limit': 0}, {'offset': -1}, {'order': 'unknown'}):
            response = self.calld.get_lines_result(
                token=VALID_TOKEN, tenant_uuid=VALID_TENANT, **params
            )
            assert_that(response.status_code, equal_to(400), params)

    def test_list_trunks_paginated(self):
        names = ['trunk-b', 'trunk-a']
        trunks = [
            MockTrunk(
                trunk_id,
                endpoint_sip={'name': name, 'registration_section_options': []},
                tenant_uuid=VALID_TENANT,
            )
            for trunk_id, name in enumerate(names, start=1)
        ]
        self.confd.set_trunks(*trunks)
        for trunk_id, _ in enumerate(names, start=1):
            self.bus.send_trunk_endpoint_associated_event(
                trunk_id, endpoint_id=trunk_id
            )
        until.assert_(self._assert_trunks_total, len(names), timeout=5)

        response = self.calld.get_trunks_result(
            token=VALID_TOKEN, tenant_uuid=VALID_TENANT, limit=1
        )

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.json(),
            has_entries(
                items=contains_exactly(has_entries(id=2, name='trunk-a')),
                total=2,
                filtered=2,
            ),
        )

    def _assert_lines_total(self, expected):
        response = self.calld.get_lines_result(
            token=VALID_TOKEN, tenant_uuid=VALID_TENANT
        )
        assert_that(response.json(), has_entries(total=expected))

    def _assert_trunks_total(self, expected):
        response = self.calld.get_trunks_result(
            token=VALID_TOKEN, tenant_uuid=VALID_TENANT
        )
        assert_that(response.json(), has_entries(total=expected))
