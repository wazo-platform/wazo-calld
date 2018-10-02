# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from unittest import TestCase
from hamcrest import (
    assert_that,
    has_entries,
)

from ..models import _Snoop
from ..schema import ApplicationSnoopSchema


class TestApplicationSnoopSchema(TestCase):

    schema = ApplicationSnoopSchema()

    def setUp(self):
        self.snooping_call_id = '1537882766.6'
        self.snooped_call_id = '1537882777.8'

    def test_load(self):
        raw_data = {
            'snooping_call_id': self.snooping_call_id,
            'whisper_mode': None,
        }

        result = self.schema.load(raw_data).data

        assert_that(result, has_entries(whisper_mode='none'))

    def test_dump(self):
        snoop = _Snoop(
            {'uuid': '7fd8f464-bdb0-4416-9b14-bf2f21be797b'},
            self.snooped_call_id,
            self.snooping_call_id,
            whisper_mode='none',
        )

        result = self.schema.dump(snoop).data
        assert_that(result, has_entries(whisper_mode=None))
