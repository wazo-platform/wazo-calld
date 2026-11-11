# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock

from hamcrest import assert_that, has_key, has_properties, is_not

from ..call import Call
from ..notifier import CallNotifier


class TestCallNotifier(TestCase):
    def setUp(self):
        self.bus = Mock()
        self.notifier = CallNotifier(self.bus)

    def _new_call(self, tenant_uuid='tenant-uuid'):
        call = Call('channel-id')
        call.channel_name = 'PJSIP/abcdef-00000001'
        call.tenant_uuid = tenant_uuid
        call.user_uuid = 'user-uuid'
        return call

    def _published_event(self):
        return self.bus.publish.call_args[0][0]

    def test_call_updated(self):
        self.notifier.call_updated(self._new_call())

        assert_that(
            self._published_event(),
            has_properties(name='call_updated', tenant_uuid='tenant-uuid'),
        )

    def test_call_updated_without_tenant_uuid(self):
        self.notifier.call_updated(self._new_call(tenant_uuid=None))

        self.bus.publish.assert_not_called()

    def test_call_dtmf_without_tenant_uuid(self):
        self.notifier.call_dtmf(self._new_call(tenant_uuid=None), '1')

        self.bus.publish.assert_not_called()

    def test_call_ended_without_tenant_uuid(self):
        self.notifier.call_ended(self._new_call(tenant_uuid=None), 16)

        self.bus.publish.assert_not_called()

    def test_user_missed_call(self):
        payload = {'user_uuid': 'user-uuid', 'reason': 'declined'}

        self.notifier.user_missed_call(payload, 'tenant-uuid', 'user-uuid')

        event = self._published_event()
        assert_that(event, has_properties(tenant_uuid='tenant-uuid'))
        assert_that(event.content, is_not(has_key('tenant_uuid')))

    def test_user_missed_call_without_tenant_uuid(self):
        payload = {'user_uuid': 'user-uuid', 'reason': 'declined'}

        self.notifier.user_missed_call(payload, None, 'user-uuid')

        self.bus.publish.assert_not_called()
