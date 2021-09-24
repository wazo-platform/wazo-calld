# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

CONFBRIDGE_NAME_PREFIX = 'wazo-meeting-'
CONFBRIDGE_NAME_SUFFIX = '-confbridge'
CONFBRIDGE_NAME_SLICE = slice(len(CONFBRIDGE_NAME_PREFIX), -len(CONFBRIDGE_NAME_SUFFIX))


class InvalidMeetingConfbridgeName(ValueError):
    def __init__(self, confbridge_name):
        self.confbridge_name = confbridge_name
        super().__init__(confbridge_name)


class AsteriskMeeting:
    def __init__(self, meeting_uuid):
        self.uuid = meeting_uuid

    @property
    def confbridge_name(self):
        return f'{CONFBRIDGE_NAME_PREFIX}{self.uuid}{CONFBRIDGE_NAME_SUFFIX}'

    @classmethod
    def from_confbridge_name(cls, confbridge_name):
        if not confbridge_name.startswith(CONFBRIDGE_NAME_PREFIX) or not confbridge_name.endswith(
            CONFBRIDGE_NAME_SUFFIX
        ):
            raise InvalidMeetingConfbridgeName(confbridge_name)

        try:
            uuid = confbridge_name[CONFBRIDGE_NAME_SLICE]
        except IndexError:
            raise InvalidMeetingConfbridgeName(confbridge_name)

        if not uuid:
            raise InvalidMeetingConfbridgeName(confbridge_name)

        return cls(uuid)
