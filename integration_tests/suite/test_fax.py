# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from hamcrest import (
    assert_that,
    calling,
    has_length,
    has_properties,
)
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from xivo_ctid_ng_client.exceptions import CtidNGError

from .helpers.base import RealAsteriskIntegrationTest
from .helpers.auth import MockUserToken
from .helpers.confd import (
    MockLine,
    MockUser,
)
from .helpers.constants import ASSET_ROOT


class TestFax(RealAsteriskIntegrationTest):

    def setUp(self):
        super().setUp()
        self.confd.reset()

    def _fax_channels(self):
        channels = self.ari.channels.list()
        fax_channels = [channel for channel in channels if channel.json['dialplan']['context'] == 'txfax']
        return fax_channels

    def test_send_fax_wrong_params(self):
        ctid_ng = self.make_ctid_ng()
        assert_that(
            calling(ctid_ng.faxes.send).with_args(
                fax_content='',
                context=None,
                extension=None,
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
            })))

    def test_send_fax_wrong_extension(self):
        ctid_ng = self.make_ctid_ng()
        assert_that(
            calling(ctid_ng.faxes.send).with_args(
                fax_content='',
                context='recipient',
                extension='not-found',
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'invalid-extension',
                'details': {
                    'exten': 'not-found',
                    'context': 'recipient',
                },
            }))
        )

    def test_send_fax_no_amid(self):
        ctid_ng = self.make_ctid_ng()
        with self.amid_stopped():
            assert_that(
                calling(ctid_ng.faxes.send).with_args(
                    fax_content='',
                    context='recipient',
                    extension='recipient-fax',
                ),
                raises(CtidNGError).matching(has_properties({
                    'status_code': 503,
                    'error_id': 'xivo-amid-error',
                }))
            )

    def test_send_fax_no_ari(self):
        ctid_ng = self.make_ctid_ng()
        with self.ari_stopped():
            assert_that(
                calling(ctid_ng.faxes.send).with_args(
                    fax_content='',
                    context='recipient',
                    extension='recipient-fax',
                ),
                raises(CtidNGError).matching(has_properties({
                    'status_code': 503,
                    'error_id': 'xivo-amid-error',
                }))
            )

    def test_send_fax_pdf_conversion_failed(self):
        ctid_ng = self.make_ctid_ng()

        # fax-failure = 1024 zeros
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax-failure.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        assert_that(
            calling(ctid_ng.faxes.send).with_args(
                fax_content,
                context='recipient',
                extension='recipient-fax',
                caller_id='fax wait'
            ), raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'fax-failure',
            }))
        )

    def test_send_fax_pdf(self):
        ctid_ng = self.make_ctid_ng()

        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        try:
            ctid_ng.faxes.send(fax_content,
                               context='recipient',
                               extension='recipient-fax',
                               caller_id='fax wait')
        except Exception as e:
            raise AssertionError('Sending fax raised an exception: {}'.format(e))

        def one_fax_channel():
            assert_that(self._fax_channels(), has_length(1))

        until.assert_(one_fax_channel, timeout=3)

    def test_send_fax_from_user_unknown(self):
        user_uuid = 'some-user-id'
        token = 'my-user-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid='my-tenant'))

        ctid_ng = self.make_ctid_ng(token)
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        assert_that(
            calling(ctid_ng.faxes.send_from_user).with_args(
                fax_content,
                extension='recipient-fax',
                caller_id='fax wait'
            ), raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'invalid-user',
            }))
        )

    def test_send_fax_from_user_without_line(self):
        user_uuid = 'some-user-id'
        token = 'my-user-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid='my-tenant'))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=[]))

        ctid_ng = self.make_ctid_ng(token)
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        assert_that(
            calling(ctid_ng.faxes.send_from_user).with_args(
                fax_content,
                extension='recipient-fax',
                caller_id='fax wait'
            ), raises(CtidNGError).matching(has_properties({
                'status_code': 400,
                'error_id': 'user-missing-main-line',
            }))
        )

    def test_send_fax_pdf_from_user(self):
        user_uuid = 'some-user-id'
        context = 'user-context'
        token = 'my-user-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid, tenant_uuid='my-tenant'))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['some-line-id']))
        self.confd.set_lines(MockLine(id='some-line-id', name='line-name', protocol='pjsip', context=context))

        ctid_ng = self.make_ctid_ng(token)
        with open(os.path.join(ASSET_ROOT, 'fax', 'fax.pdf'), 'rb') as fax_file:
            fax_content = fax_file.read()

        try:
            ctid_ng.faxes.send_from_user(fax_content,
                                         extension='recipient-fax',
                                         caller_id='fax wait')
        except Exception as e:
            raise AssertionError('Sending fax raised an exception: {}'.format(e))

        def one_fax_channel():
            assert_that(self._fax_channels(), has_length(1))

        until.assert_(one_fax_channel, timeout=3)
