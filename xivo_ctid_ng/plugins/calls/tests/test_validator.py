# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from unittest import TestCase

from ..exceptions import CallCreationError
from .. import validator


class TestCallsValidator(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_validate_originate_body_with_no_source_key(self):
        body = {
            'destination': {'priority': '1',
                            'extension': 'my-exten',
                            'context': 'my-context'}
        }

        self.assertRaises(CallCreationError, validator.validate_originate_body, body)

    def test_validate_originate_body_with_no_destination_key(self):
        body = {
            'source': {'user': 'abcd'}
        }

        self.assertRaises(CallCreationError, validator.validate_originate_body, body)

    def test_validate_originate_body_with_no_source_user(self):
        body = {
            'destination': {'priority': '1',
                            'extension': 'my-exten',
                            'context': 'my-context'},
            'source': {}
        }

        self.assertRaises(CallCreationError, validator.validate_originate_body, body)

    def test_validate_originate_body_with_no_destination_priority(self):
        body = {
            'destination': {'extension': 'my-exten',
                            'context': 'my-context'},
            'source': {'user': 'abcd'}
        }

        self.assertRaises(CallCreationError, validator.validate_originate_body, body)

    def test_validate_originate_body_with_no_destination_extension(self):
        body = {
            'destination': {'priority': '1',
                            'context': 'my-context'},
            'source': {'user': 'abcd'}
        }

        self.assertRaises(CallCreationError, validator.validate_originate_body, body)

    def test_validate_originate_body_with_no_destination_context(self):
        body = {
            'destination': {'priority': '1',
                            'extension': 'my-exten'},
            'source': {'user': 'abcd'}
        }

        self.assertRaises(CallCreationError, validator.validate_originate_body, body)
