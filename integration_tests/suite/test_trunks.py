# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, contains, has_entries

from .helpers.ari_ import MockEndpoint
from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id
from .helpers.confd import MockTrunk
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


class TestBusConsume(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_list_matches_confd_trunks(self):
        name = 'abcdef'
        trunk_id = 42
        tenant_uuid = 'tenant_uuid'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'online', channel_ids=[new_call_id(), new_call_id(leap=1)])
        )
        self.confd.set_trunks(
            MockTrunk(
                trunk_id,
                endpoint_sip={'name': name, 'username': 'the-username'},
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')
        self.reset_clients()
        self.wait_strategy.wait(self)

        result = self.calld.list_trunks()

        assert_that(
            result, has_entries(
                items=contains(
                    has_entries(
                        id=trunk_id,
                        name=name,
                        registered=True,
                        current_call_count=2,
                    )
                ),
                total=1,
            )
        )
