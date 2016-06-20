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
from xivo_ctid_ng.plugins.presences.resources import user_presence_request_schema


class TestUserPresenceRequestSchema(unittest.TestCase):

    schema = user_presence_request_schema

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


class TestPresenceRequestSchema(unittest.TestCase):

    schema = presence_request_schema

    def setUp(self):
        self.user_uuid = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.data = {
            'user_uuid': self.user_uuid,
            'status_name': 'available'
        }

    def test_valid(self):
        result = self.schema.load(self.data).data

        assert_that(result['user_uuid'], equal_to(uuid.UUID(self.user_uuid)))
        assert_that(result['status_name'], equal_to('available'))

    def test_invalid_status_name(self):
        self.data['status_name'] = None

        assert_that(calling(self.schema.load).with_args(self.data), raises(ValidationError))

    def test_invalid_user_uuid(self):
        self.data['user_uuid'] = 'not-an-uuid'

        assert_that(calling(self.schema.load).with_args(self.data), raises(ValidationError))
