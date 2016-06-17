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

from xivo_ctid_ng.plugins.chats.resources import chat_request_schema
from xivo_ctid_ng.plugins.chats.resources import user_chat_request_schema


class TestUserChatRequestSchema(unittest.TestCase):

    schema = user_chat_request_schema

    def setUp(self):
        self.to = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.to_xivo_uuid = 'ba447787-5577-4d2c-9758-7d35926ff07f'
        self.data = {
            'alias': 'alice',
            'msg': 'hello',
            'to': self.to,
            'to_xivo_uuid': self.to_xivo_uuid,
        }

    def test_valid(self):
        result = self.schema.load(self.data).data

        assert_that(result['alias'], equal_to('alice'))
        assert_that(result['msg'], equal_to('hello'))
        assert_that(result['to'], equal_to(uuid.UUID(self.to)))
        assert_that(result['to_xivo_uuid'], equal_to(uuid.UUID(self.to_xivo_uuid)))

    def test_invalid_to(self):
        self.data['to'] = 'not-an-uuid'

        assert_that(calling(self.schema.load).with_args(self.data), raises(ValidationError))

    def test_invalid_to_xivo_uuid(self):
        self.data['to_xivo_uuid'] = 'not-an-uuid'

        assert_that(calling(self.schema.load).with_args(self.data), raises(ValidationError))

    def test_xivo_uuid_not_required(self):
        del self.data['to_xivo_uuid']

        result = self.schema.load(self.data).data

        assert_that('to_xivo_uuid' not in result)


class TestChatRequestSchema(unittest.TestCase):

    schema = chat_request_schema

    def setUp(self):
        self.to = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.to_xivo_uuid = 'ba447787-5577-4d2c-9758-7d35926ff07f'
        self.from_ = '795f9b8c-d7e4-4183-8619-50384370cad2'
        self.data = {
            'alias': 'alice',
            'msg': 'hello',
            'to': self.to,
            'to_xivo_uuid': self.to_xivo_uuid,
            'from': self.from_,
        }

    def test_valid(self):
        result = self.schema.load(self.data).data

        assert_that(result['alias'], equal_to('alice'))
        assert_that(result['msg'], equal_to('hello'))
        assert_that(result['to'], equal_to(uuid.UUID(self.to)))
        assert_that(result['to_xivo_uuid'], equal_to(uuid.UUID(self.to_xivo_uuid)))
        assert_that(result['from'], equal_to(uuid.UUID(self.from_)))

    def test_invalid_from(self):
        self.data['from'] = 'not-an-uuid'

        assert_that(calling(self.schema.load).with_args(self.data), raises(ValidationError))
