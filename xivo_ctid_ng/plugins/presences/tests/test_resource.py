# -*- coding: utf-8 -*-
# Copyright 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import unittest
import uuid

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import equal_to
from hamcrest import raises
from marshmallow import ValidationError

from xivo_ctid_ng.plugins.presences.resources import presence_request_schema


class TestPresenceRequestSchema(unittest.TestCase):

    schema = presence_request_schema

    def setUp(self):
        self.data = {
            'status_name': 'available'
        }

    def test_valid(self):
        result = self.schema.load(self.data).data

        assert_that(result['status_name'], equal_to('available'))

    def test_invalid_status_name(self):
        self.data['status_name'] = None

        assert_that(calling(self.schema.load).with_args(self.data), raises(ValidationError))
