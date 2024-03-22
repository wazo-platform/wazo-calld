# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

from pytest import raises

import wazo_calld.plugins.parking_lots.helpers as helpers

DATETIME = f'{helpers.__name__}.datetime'


class TestCamelCaseToSnake(TestCase):
    def test_camel_to_snake(self) -> None:
        assert helpers.camel_to_snake('HelloWorld') == 'hello_world'
        assert helpers.camel_to_snake('HTTPError') == 'http_error'
        assert helpers.camel_to_snake('AbCdEfGh') == 'ab_cd_ef_gh'


class TestSplitParkingID(TestCase):
    def test_split_parking_id(self) -> None:
        assert helpers.split_parking_id_from_name('parkinglot-1') == 1
        assert (
            helpers.split_parking_id_from_name('parkinglot-50424240342402')
            == 50424240342402
        )

        with raises(ValueError):
            helpers.split_parking_id_from_name('default')
            helpers.split_parking_id_from_name('parking_lot-1')


@patch(f'{DATETIME}', Mock(now=Mock(return_value=datetime(2000, 1, 1, 0, 0))))
class TestTimestamp(TestCase):
    def test_timestamp_zero(self) -> None:
        assert helpers.timestamp(0) is None
        assert helpers.timestamp('0') is None

    def test_timestamp_empty(self) -> None:
        assert helpers.timestamp('') is None

    def test_timestamp_none(self) -> None:
        assert helpers.timestamp(None) is None  # type: ignore[arg-type]

    def test_timestamp_overflow(self) -> None:
        max_unsigned = sys.maxsize * 2 + 1
        assert helpers.timestamp(max_unsigned) is None

    def test_timestamp(self) -> None:
        assert helpers.timestamp(1) == '2000-01-01T00:00:01'
        assert helpers.timestamp('1') == '2000-01-01T00:00:01'
        assert helpers.timestamp(10) == '2000-01-01T00:00:10'
        assert helpers.timestamp('10') == '2000-01-01T00:00:10'
        assert helpers.timestamp(60) == '2000-01-01T00:01:00'
        assert helpers.timestamp('60') == '2000-01-01T00:01:00'
        assert helpers.timestamp(3601) == '2000-01-01T01:00:01'
        assert helpers.timestamp('3601') == '2000-01-01T01:00:01'
        assert helpers.timestamp(1234567) == '2000-01-15T06:56:07'
        assert helpers.timestamp('1234567') == '2000-01-15T06:56:07'

    def test_timestamp_negative(self) -> None:
        assert helpers.timestamp(-1) == '1999-12-31T23:59:59'
        assert helpers.timestamp('-1') == '1999-12-31T23:59:59'
        assert helpers.timestamp(-3601) == '1999-12-31T22:59:59'
        assert helpers.timestamp('-3601') == '1999-12-31T22:59:59'

    def test_timestamp_since(self) -> None:
        assert helpers.timestamp_since(1) == '1999-12-31T23:59:59'
        assert helpers.timestamp_since(-1) == '1999-12-31T23:59:59'

    def test_timestamp_since_overflow(self) -> None:
        max_unsigned = sys.maxsize * 2 + 1
        with raises(OverflowError):
            helpers.timestamp_since(max_unsigned)

    def test_timestamp_invalid_string(self) -> None:
        with raises(ValueError):
            helpers.timestamp('ABCDEF')
            helpers.timestamp('None')
            helpers.timestamp('null')
