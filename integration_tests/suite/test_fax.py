# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from hamcrest import (
    assert_that,
    calling,
    empty,
    has_entries,
    has_items,
    has_length,
    has_properties,
    is_not,
)
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.confd import MockLine, MockUser
from .helpers.constants import ASSET_ROOT, VALID_TENANT, VALID_TOKEN
from .helpers.real_asterisk import RealAsteriskIntegrationTest


class TestFax(RealAsteriskIntegrationTest):
    asset = 'real_asterisk_fax'

    def setUp(self):
        super().setUp()
        self.confd.reset()
        self.calld_client.set_token(VALID_TOKEN)

    def _fax_channels(self):
        channels = self.ari.channels.list()
        fax_channels = [
            channel
            for channel in channels
            if channel.json['dialplan']['context'] == 'txfax'
        ]
        return fax_channels

    def test_send_fax_wrong_params(self):
        assert_that(
            calling(self.calld_client.faxes.send).with_args(
                fax_content='',
                context=None,
                extension=None,
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                    }
                )
            ),
        )

    def test_send_fax_wrong_extension(self):
        assert_that(
            calling(self.calld_client.faxes.send).with_args(
                fax_content='',
                context='recipient',
                extension='not-found',
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'invalid-extension',
                        'details': {
                            'exten': 'not-found',
                            'context': 'recipient',
                        },
                    }
                )
            ),
        )

    def test_send_fax_no_amid(self):
        with self.amid_stopped():
            assert_that(
                calling(self.calld_client.faxes.send).with_args(
                    fax_content='',
                    context='recipient',
                    extension='recipient-fax',
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )

    def test_send_fax_no_ari(self):
        with self.ari_stopped():
            assert_that(
                calling(self.calld_client.faxes.send).with_args(
                    fax_content='',
                    context='recipient',
                    extension='recipient-fax',
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )

    def test_send_fax_pdf_conversion_failed(self):
        # fax-failure = 1024 zeros
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax-failure.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        assert_that(
            calling(self.calld_client.faxes.send).with_args(
                fax_content,
                context='recipient',
                extension='recipient-fax',
                caller_id='fax wait',
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'fax-failure',
                    }
                )
            ),
        )

    def test_send_fax_pdf(self):
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        fax = self.calld_client.faxes.send(
            fax_content,
            context='recipient',
            extension='recipient-fax',
            caller_id='fax wait',
            ivr_extension='12',
            wait_time=42,
        )

        assert_that(
            fax,
            has_entries(
                {
                    'id': is_not(empty()),
                    'context': 'recipient',
                    'extension': 'recipient-fax',
                    'caller_id': 'fax wait',
                    'ivr_extension': '12',
                    'wait_time': 42,
                }
            ),
        )

        def one_fax_channel():
            assert_that(self._fax_channels(), has_length(1))

        until.assert_(one_fax_channel, timeout=10)

    def test_send_fax_events_success(self):
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        events = self.bus.accumulator(headers={'tenant_uuid': VALID_TENANT})

        result = self.calld_client.faxes.send(
            fax_content,
            context='recipient',
            extension='recipient-fax',
            caller_id='fax success',
        )
        fax_id = result['id']

        def bus_events_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_created',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'recipient',
                                        'extension': 'recipient-fax',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_created',
                                'tenant_uuid': VALID_TENANT,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_succeeded',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'recipient',
                                        'extension': 'recipient-fax',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_succeeded',
                                'tenant_uuid': VALID_TENANT,
                            }
                        ),
                    ),
                ),
            )

        until.assert_(bus_events_received, timeout=10)

    def test_send_fax_events_success_when_extension_contains_whitespace(self):
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        events = self.bus.accumulator(headers={'tenant_uuid': VALID_TENANT})

        result = self.calld_client.faxes.send(
            fax_content,
            context='recipient',
            extension='rec ip\nie\rnt-f\tax',
            caller_id='fax success',
        )
        fax_id = result['id']

        def bus_events_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_created',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'recipient',
                                        'extension': 'recipient-fax',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_created',
                                'tenant_uuid': VALID_TENANT,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_succeeded',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'recipient',
                                        'extension': 'recipient-fax',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_succeeded',
                                'tenant_uuid': VALID_TENANT,
                            }
                        ),
                    ),
                ),
            )

        until.assert_(bus_events_received, timeout=10)

    def test_send_fax_events_failure(self):
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        events = self.bus.accumulator(headers={'tenant_uuid': VALID_TENANT})

        result = self.calld_client.faxes.send(
            fax_content,
            context='recipient',
            extension='recipient-fax',
            caller_id='fax fail',
        )
        fax_id = result['id']

        def bus_events_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_created',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'recipient',
                                        'extension': 'recipient-fax',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_created',
                                'tenant_uuid': VALID_TENANT,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_failed',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'recipient',
                                        'extension': 'recipient-fax',
                                        'error': 'error explanation',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_failed',
                                'tenant_uuid': VALID_TENANT,
                            }
                        ),
                    ),
                ),
            )

        until.assert_(bus_events_received, timeout=10)

    def test_send_fax_from_user_unknown(self):
        user_uuid = 'some-user-id'
        calld_client = self.make_user_calld(user_uuid)

        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        assert_that(
            calling(calld_client.faxes.send_from_user).with_args(
                fax_content, extension='recipient-fax', caller_id='fax wait'
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'invalid-user',
                    }
                )
            ),
        )

    def test_send_fax_from_user_without_line(self):
        tenant_uuid = 'some-tenant-uuid'
        user_uuid = 'some-user-id'
        self.confd.set_users(
            MockUser(uuid=user_uuid, line_ids=[], tenant_uuid=tenant_uuid)
        )
        calld_client = self.make_user_calld(user_uuid, tenant_uuid=tenant_uuid)

        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        assert_that(
            calling(calld_client.faxes.send_from_user).with_args(
                fax_content, extension='recipient-fax', caller_id='fax wait'
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'user-missing-main-line',
                    }
                )
            ),
        )

    def test_send_fax_pdf_from_user(self):
        tenant_uuid = 'some-tenant-uuid'
        user_uuid = 'some-user-id'
        context = 'user-context'
        self.confd.set_users(
            MockUser(uuid=user_uuid, line_ids=['some-line-id'], tenant_uuid=tenant_uuid)
        )
        self.confd.set_lines(
            MockLine(
                id='some-line-id',
                name='line-name',
                protocol='pjsip',
                context=context,
                tenant_uuid=tenant_uuid,
            )
        )
        calld_client = self.make_user_calld(user_uuid, tenant_uuid=tenant_uuid)

        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        try:
            fax = calld_client.faxes.send_from_user(
                fax_content,
                extension='recipient-fax',
                caller_id='fax wait',
                ivr_extension='12',
                wait_time=42,
            )
        except Exception as e:
            raise AssertionError(f'Sending fax raised an exception: {e}')

        assert_that(
            fax,
            has_entries(
                {
                    'id': is_not(empty()),
                    'context': context,
                    'extension': 'recipient-fax',
                    'caller_id': 'fax wait',
                    'ivr_extension': '12',
                    'wait_time': 42,
                }
            ),
        )

        def one_fax_channel():
            assert_that(self._fax_channels(), has_length(1))

        until.assert_(one_fax_channel, timeout=3)

    def test_send_fax_from_user_events_success(self):
        tenant_uuid = 'my-tenant'
        user_uuid = 'some-user-id'
        context = 'user-context'
        self.confd.set_users(
            MockUser(uuid=user_uuid, line_ids=['some-line-id'], tenant_uuid=tenant_uuid)
        )
        self.confd.set_lines(
            MockLine(
                id='some-line-id',
                name='line-name',
                protocol='pjsip',
                context=context,
                tenant_uuid=tenant_uuid,
            )
        )
        calld_client = self.make_user_calld(user_uuid, tenant_uuid=tenant_uuid)

        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        events = self.bus.accumulator(headers={f'user_uuid:{user_uuid}': True})

        result = calld_client.faxes.send_from_user(
            fax_content, extension='recipient-fax', caller_id='fax success'
        )
        fax_id = result['id']

        def bus_events_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_user_created',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'user-context',
                                        'extension': 'recipient-fax',
                                        'user_uuid': 'some-user-id',
                                        'tenant_uuid': tenant_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_user_created',
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_user_succeeded',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'user-context',
                                        'extension': 'recipient-fax',
                                        'user_uuid': 'some-user-id',
                                        'tenant_uuid': 'my-tenant',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_user_succeeded',
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    ),
                ),
            )

        until.assert_(bus_events_received, timeout=10)

    def test_send_fax_from_user_events_success_when_extension_contains_whitespace(self):
        tenant_uuid = 'my-tenant'
        user_uuid = 'some-user-id'
        context = 'user-context'
        self.confd.set_users(
            MockUser(uuid=user_uuid, line_ids=['some-line-id'], tenant_uuid=tenant_uuid)
        )
        self.confd.set_lines(
            MockLine(
                id='some-line-id',
                name='line-name',
                protocol='pjsip',
                context=context,
                tenant_uuid=tenant_uuid,
            )
        )
        calld_client = self.make_user_calld(user_uuid, tenant_uuid=tenant_uuid)

        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        events = self.bus.accumulator(headers={f'user_uuid:{user_uuid}': True})

        result = calld_client.faxes.send_from_user(
            fax_content, extension='rec ip\nie\rnt-f\tax', caller_id='fax success'
        )
        fax_id = result['id']

        def bus_events_received():
            assert_that(
                events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_user_created',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'user-context',
                                        'extension': 'recipient-fax',
                                        'user_uuid': 'some-user-id',
                                        'tenant_uuid': tenant_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_user_created',
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'fax_outbound_user_succeeded',
                                'data': has_entries(
                                    {
                                        'id': fax_id,
                                        'context': 'user-context',
                                        'extension': 'recipient-fax',
                                        'user_uuid': 'some-user-id',
                                        'tenant_uuid': tenant_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'fax_outbound_user_succeeded',
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    ),
                ),
            )

        until.assert_(bus_events_received, timeout=10)
