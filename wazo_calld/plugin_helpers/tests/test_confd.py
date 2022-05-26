# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from hamcrest import (
    assert_that,
    calling,
    equal_to,
    raises,
)
from unittest.mock import Mock
from unittest import TestCase

from ..confd import Line
from ..exceptions import WazoConfdUnreachable


class TestLine(TestCase):

    def setUp(self):
        self.confd_client = Mock()
        self.line = Line(42, self.confd_client)

    def test_request_exception_is_transformed_in_confd_exception(self):
        self.confd_client.lines.get.side_effect = requests.RequestException

        assert_that(calling(self.line._get).with_args(),
                    raises(WazoConfdUnreachable))

    def test_line_interface_autoanswer_sip(self):
        self.confd_client.lines.get.return_value = {
            'protocol': 'sip',
            'name': 'abcdef',
        }
        assert_that(self.line.interface_autoanswer(), equal_to('pjsip/abcdef'))

    def test_line_interface_autoanswer_sccp(self):
        self.confd_client.lines.get.return_value = {
            'protocol': 'sccp',
            'name': 'abcdef',
        }
        assert_that(self.line.interface_autoanswer(), equal_to('sccp/abcdef/autoanswer'))
