# Copyright 2021-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    calling,
    raises,
)
from unittest import TestCase

from ..meeting import (
    AsteriskMeeting,
    InvalidMeetingConfbridgeName,
)


class TestBusConsume(TestCase):
    def test_confbridge_name(self):
        assert AsteriskMeeting('uuid').confbridge_name == 'wazo-meeting-uuid-confbridge'

    def test_from_confbridge_name(self):
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(''),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args('something'),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(
                'wazo-meeting.uuid.confbridge'
            ),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(
                'wazo-meeting-uuid.confbridge'
            ),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(
                'wazo-meeting.uuid-confbridge'
            ),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(
                'wazo-meeting-uuid-confbridge.'
            ),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(
                '.wazo-meeting.uuid-confbridge'
            ),
            raises(InvalidMeetingConfbridgeName),
        )
        assert_that(
            calling(AsteriskMeeting.from_confbridge_name).with_args(
                'wazo-meeting--confbridge'
            ),
            raises(InvalidMeetingConfbridgeName),
        )
        assert (
            AsteriskMeeting.from_confbridge_name('wazo-meeting-uuid-confbridge').uuid
            == 'uuid'
        )
