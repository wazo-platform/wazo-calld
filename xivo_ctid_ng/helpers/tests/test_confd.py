# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import raises
from mock import Mock
from unittest import TestCase

from xivo_ctid_ng.exceptions import XiVOConfdUnreachable
from ..confd import Line


class TestLine(TestCase):

    def setUp(self):
        self.confd_client = Mock()
        self.line = Line(42, self.confd_client)

    def test_request_exception_is_transformed_in_confd_exception(self):
        self.confd_client.lines.get.side_effect = requests.RequestException

        assert_that(calling(self.line._get).with_args(),
                    raises(XiVOConfdUnreachable))
