# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import unittest

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import equal_to
from hamcrest import raises
from marshmallow import ValidationError

from ..resources import MessageRequestSchema


class TestMessageRequestSchema(unittest.TestCase):

    schema = MessageRequestSchema

    def setUp(self):
        self.author = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.server = 'ba447787-5577-4d2c-9758-7d35926ff07f'
        self.receiver = '795f9b8c-d7e4-4183-8619-50384370cad2'
        self.data = {
            'author': self.author,
            'server': self.server,
            'receiver': self.receiver,
            'message': 'hello',
        }

    def test_valid(self):
        result = self.schema().load(self.data).data

        assert_that(result['message'], equal_to('hello'))
        assert_that(result['author'], equal_to(self.author))
        assert_that(result['server'], equal_to(self.server))
        assert_that(result['receiver'], equal_to(self.receiver))

    def test_invalid_from(self):
        self.data['author'] = 1234

        assert_that(calling(self.schema().load).with_args(self.data), raises(ValidationError))
