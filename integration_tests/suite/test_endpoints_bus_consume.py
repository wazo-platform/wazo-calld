# Copyright 2019-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_item
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id
from .helpers.constants import XIVO_UUID
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy
from .helpers.ari_ import MockEndpoint
from .helpers.confd import MockLine, MockTrunk


class TestTrunkBusConsume(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_when_ami_hangup_then_bus_event(self):
        call_id = new_call_id()
        trunk_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'online', channel_ids=[call_id, new_call_id(leap=1)])
        )
        self.confd.set_trunks(
            MockTrunk(
                trunk_id,
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', 'the-username']],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='trunks.{}.status.updated'.format(trunk_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_hangup_event(call_id, channel='PJSIP/abcdef-00000001')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=trunk_id,
                    technology='sip',
                    name='abcdef',
                    current_call_count=1,
                )
            )))

        until.assert_(assert_function, tries=5)

    def test_when_ami_newchannel_then_bus_event(self):
        trunk_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'online', channel_ids=[new_call_id(), new_call_id(leap=1)])
        )
        self.confd.set_trunks(
            MockTrunk(
                trunk_id,
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', 'the-username']],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='trunks.{}.status.updated'.format(trunk_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_newchannel_event(new_call_id(leap=2), channel='PJSIP/abcdef-00000001')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=trunk_id,
                    technology='sip',
                    name='abcdef',
                    current_call_count=3,
                )
            )))

        until.assert_(assert_function, tries=5)

    def test_when_ami_peerstatus_then_bus_event(self):
        trunk_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'offline'),
        )
        self.confd.set_trunks(
            MockTrunk(
                trunk_id,
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', 'the-username']],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='trunks.{}.status.updated'.format(trunk_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_peerstatus_event('PJSIP', 'PJSIP/abcdef', 'Reachable')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=trunk_id,
                    technology='sip',
                    name='abcdef',
                    registered=True,
                )
            )))

        until.assert_(assert_function, tries=5)

        self.bus.send_ami_peerstatus_event('PJSIP', 'PJSIP/abcdef', 'Unreachable')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=trunk_id,
                    technology='sip',
                    name='abcdef',
                    registered=False,
                )
            )))

        until.assert_(assert_function, tries=5)

    def test_when_ami_registry_then_bus_event(self):
        trunk_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'
        username = 'the-username'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'offline'),
        )
        self.confd.set_trunks(
            MockTrunk(
                trunk_id,
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', username]],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='trunks.{}.status.updated'.format(trunk_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_registry_event(
            'PJSIP', 'sip:here', 'Registered', 'sip:{}@here'.format(username),
        )

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=trunk_id,
                    technology='sip',
                    name='abcdef',
                    registered=True,
                )
            )))

        until.assert_(assert_function, tries=5)

        self.bus.send_ami_registry_event(
            'PJSIP', 'sip:here', 'Unregistered', 'sip:{}@here'.format(username),
        )

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=trunk_id,
                    technology='sip',
                    name='abcdef',
                    registered=False,
                )
            )))

        until.assert_(assert_function, tries=5)

    def test_when_trunk_associated_events_can_be_published(self):
        trunk_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'
        username = 'the-username'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'offline', channel_ids=[]),
        )
        # There are no trunks when starting calld

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='trunks.{}.status.updated'.format(trunk_id))
        self.reset_clients()
        self.wait_strategy.wait(self)

        # A trunk is created
        self.confd.set_trunks(
            MockTrunk(
                trunk_id,
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', username]],
                },
                tenant_uuid=tenant_uuid,
            )
        )
        self.bus.send_trunk_endpoint_associated_event(trunk_id, endpoint_id=3)

        self.bus.send_ami_registry_event(
            'PJSIP', 'sip:here', 'Registered', 'sip:{}@here'.format(username),
        )

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='trunk_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(id=trunk_id),
            )))

        until.assert_(assert_function, tries=5)


class TestLineBusConsume(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_when_ami_hangup_then_bus_event(self):
        call_id = new_call_id()
        line_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'online', channel_ids=[call_id, new_call_id(leap=1)])
        )
        self.confd.set_lines(
            MockLine(
                line_id,
                name=name,
                protocol='sip',
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', 'the-username']],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='lines.{}.status.updated'.format(line_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_hangup_event(call_id, channel='PJSIP/abcdef-00000001')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='line_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=line_id,
                    technology='sip',
                    name='abcdef',
                    current_call_count=1,
                )
            )))

        until.assert_(assert_function, tries=5)

    def test_when_ami_newchannel_then_bus_event(self):
        line_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'online', channel_ids=[new_call_id(), new_call_id(leap=1)])
        )
        self.confd.set_lines(
            MockLine(
                line_id,
                name=name,
                protocol='sip',
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', 'the-username']],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='lines.{}.status.updated'.format(line_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_newchannel_event(new_call_id(leap=2), channel='PJSIP/abcdef-00000001')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='line_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=line_id,
                    technology='sip',
                    name='abcdef',
                    current_call_count=3,
                )
            )))

        until.assert_(assert_function, tries=5)

    def test_when_ami_peerstatus_then_bus_event(self):
        line_id = 42
        tenant_uuid = 'the_tenant_uuid'
        name = 'abcdef'

        self.ari.set_endpoints(
            MockEndpoint('PJSIP', name, 'offline'),
        )
        self.confd.set_lines(
            MockLine(
                line_id,
                name=name,
                protocol='sip',
                endpoint_sip={
                    'name': name,
                    'auth_section_options': [['username', 'the-username']],
                },
                tenant_uuid=tenant_uuid,
            )
        )

        self.restart_service('calld')

        events = self.bus.accumulator(routing_key='lines.{}.status.updated'.format(line_id))
        self.reset_clients()
        self.wait_strategy.wait(self)
        self.bus.send_ami_peerstatus_event('PJSIP', 'PJSIP/abcdef', 'Reachable')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='line_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=line_id,
                    technology='sip',
                    name='abcdef',
                    registered=True,
                )
            )))

        until.assert_(assert_function, tries=5)

        self.bus.send_ami_peerstatus_event('PJSIP', 'PJSIP/abcdef', 'Unreachable')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries(
                name='line_status_updated',
                origin_uuid=XIVO_UUID,
                data=has_entries(
                    id=line_id,
                    technology='sip',
                    name='abcdef',
                    registered=False,
                )
            )))

        until.assert_(assert_function, tries=5)
