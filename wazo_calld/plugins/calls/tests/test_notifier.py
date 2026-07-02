# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock

from hamcrest import assert_that, calling, not_, raises

from ..call import Call
from ..notifier import CallNotifier


class TestCallNotifier(TestCase):
    def setUp(self):
        self.bus = Mock()
        self.notifier = CallNotifier(self.bus)

    def _make_call(self, tenant_uuid='tenant-uuid'):
        call = Call('1234567890.42')
        call.tenant_uuid = tenant_uuid
        call.user_uuid = 'user-uuid'
        return call

    def test_call_updated_without_tenant_does_not_raise_and_does_not_publish(self):
        call = self._make_call(tenant_uuid=None)

        assert_that(
            calling(self.notifier.call_updated).with_args(call),
            not_(raises(Exception)),
        )
        self.bus.publish.assert_not_called()

    def test_call_updated_with_empty_tenant_does_not_publish(self):
        call = self._make_call(tenant_uuid='')

        assert_that(
            calling(self.notifier.call_updated).with_args(call),
            not_(raises(Exception)),
        )
        self.bus.publish.assert_not_called()

    def test_call_updated_with_tenant_publishes(self):
        call = self._make_call()

        self.notifier.call_updated(call)

        self.bus.publish.assert_called_once()

    def test_user_missed_call_with_empty_tenant_does_not_publish(self):
        payload = {
            'user_uuid': 'user-uuid',
            'tenant_uuid': '',
            'caller_user_uuid': None,
            'caller_id_name': 'Alice',
            'caller_id_number': '1001',
            'dialed_extension': '1002',
            'conversation_id': '1234567890.42',
            'reason': 'no-answer',
        }

        assert_that(
            calling(self.notifier.user_missed_call).with_args(payload),
            not_(raises(Exception)),
        )
        self.bus.publish.assert_not_called()
