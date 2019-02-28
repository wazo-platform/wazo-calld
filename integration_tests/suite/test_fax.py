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

from .helpers.constants import ASSET_ROOT
from .helpers.base import RealAsteriskIntegrationTest


class TestFax(RealAsteriskIntegrationTest):

    def _fax_channels(self):
        channels = self.ari.channels.list()
        fax_channels = [channel for channel in channels if channel.json['dialplan']['context'] == 'txfax']
        return fax_channels

    def test_send_fax_wrong_params(self):
        ctid_ng = self.make_ctid_ng()
        assert_that(
            calling(ctid_ng.fax.send).with_args(
                fax_content='',
                context=None,
                extension=None,
            ),
            raises(CtidNGError).matching(has_properties({
                'status_code': 400,
            })))

    def test_send_fax_tiff(self):
        ctid_ng = self.make_ctid_ng()
        fax_content = open(os.path.join(ASSET_ROOT, 'fax', 'fax.tiff'), 'rb').read()

        try:
            ctid_ng.fax.send(fax_content,
                             context='recipient',
                             extension='recipient-fax',
                             user_id='my-user-id',
                             caller_id='fax wait')
        except Exception as e:
            raise AssertionError('Sending fax raised an exception: {}'.format(e))

        def one_fax_channel():
            assert_that(self._fax_channels(), has_length(1))

        until.assert_(one_fax_channel, timeout=3)
