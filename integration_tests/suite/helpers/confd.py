# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from random import choice
from string import ascii_uppercase, digits

import requests

from .schemas import ExtensionSchema, ParkingLotSchema


class ConfdClient:
    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        return f'http://{self._host}:{self._port}/{"/".join(parts)}'

    def is_up(self):
        url = self.url()
        try:
            response = requests.get(url)
            return response.status_code == 404
        except requests.RequestException:
            return False

    def set_applications(self, *mock_applications):
        url = self.url('_set_response')
        body = {
            'response': 'applications',
            'content': {app.uuid(): app.to_dict() for app in mock_applications},
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_users(self, *mock_users):
        url = self.url('_set_response')
        body = {
            'response': 'users',
            'content': {user.uuid(): user.to_dict() for user in mock_users},
        }
        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_lines(self, *mock_lines):
        url = self.url('_set_response')
        body = {
            'response': 'lines',
            'content': {line.id_(): line.to_dict() for line in mock_lines},
        }
        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_user_lines(self, set_user_lines):
        content = {}
        for user, user_lines in set_user_lines.items():
            content[user] = [user_line.to_dict() for user_line in user_lines]

        url = self.url('_set_response')
        body = {'response': 'user_lines', 'content': content}
        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_user_voicemails(self, set_user_voicemails):
        content = {}
        for user, voicemails in set_user_voicemails.items():
            content[user] = [voicemail.to_dict() for voicemail in voicemails]

        url = self.url('_set_response')
        body = {'response': 'user_voicemails', 'content': content}
        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_switchboards(self, *mock_switchboards):
        url = self.url('_set_response')
        body = {
            'response': 'switchboards',
            'content': {
                switchboard.uuid(): switchboard.to_dict()
                for switchboard in mock_switchboards
            },
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_switchboard_fallbacks(self, *mock_switchboard_fallbacks):
        url = self.url('_set_response')
        body = {
            'response': 'switchboard_fallbacks',
            'content': {
                switchboard_fallback.uuid(): switchboard_fallback.to_dict()
                for switchboard_fallback in mock_switchboard_fallbacks
            },
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_conferences(self, *mock_conferences):
        url = self.url('_set_response')
        body = {
            'response': 'conferences',
            'content': {
                conference.id(): conference.to_dict() for conference in mock_conferences
            },
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_meetings(self, *mock_meetings):
        url = self.url('_set_response')
        body = {
            'response': 'meetings',
            'content': {meeting.uuid(): meeting.to_dict() for meeting in mock_meetings},
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_moh(self, *mock_mohs):
        url = self.url('_set_response')
        body = {
            'response': 'moh',
            'content': {moh.uuid(): moh.to_dict() for moh in mock_mohs},
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_parkinglots(self, *mock_parkings: MockParkinglot):
        url = self.url('_set_response')
        body = {
            'response': 'parkinglots',
            'content': {parking.id(): parking.to_dict() for parking in mock_parkings},
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_trunks(self, *mock_trunks):
        url = self.url('_set_response')
        body = {
            'response': 'trunks',
            'content': {trunk.id(): trunk.to_dict() for trunk in mock_trunks},
        }

        response = requests.post(url, json=body)
        response.raise_for_status()

    def set_voicemails(self, *mock_voicemails):
        url = self.url('_set_response')
        body = {
            'response': 'voicemails',
            'content': {
                voicemail.id(): voicemail.to_dict() for voicemail in mock_voicemails
            },
        }
        response = requests.post(url, json=body)
        response.raise_for_status()

    def reset(self):
        url = self.url('_reset')
        response = requests.post(url)
        response.raise_for_status()

    def requests(self):
        url = self.url('_requests')
        response = requests.get(url)
        response.raise_for_status()
        return response.json()


class MockApplication:
    def __init__(
        self,
        uuid,
        name,
        tenant_uuid=None,
        destination=None,
        type_=None,
        moh=None,
        answer=None,
    ):
        self._uuid = uuid
        self._tenant_uuid = tenant_uuid
        self._name = name
        self._destination = destination
        self._destination_options = {}
        if type_:
            self._destination_options['type'] = type_
        if moh:
            self._destination_options['music_on_hold'] = moh
        if answer:
            self._destination_options['answer'] = answer

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
            'tenant_uuid': self._tenant_uuid,
            'name': self._name,
            'destination': self._destination,
            'destination_options': self._destination_options,
        }


class MockMoh:
    def __init__(self, uuid, name='default'):
        self._uuid = uuid
        self._name = name

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
            'name': self._name,
        }


class MockUser:
    def __init__(
        self, uuid, line_ids=None, mobile=None, voicemail=None, tenant_uuid=None
    ):
        self._uuid = uuid
        self._line_ids = line_ids or []
        self._mobile = mobile
        self._voicemail = voicemail
        self._tenant_uuid = tenant_uuid

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
            'lines': [{'id': line_id} for line_id in self._line_ids],
            'mobile_phone_number': self._mobile,
            'voicemail': self._voicemail,
            'tenant_uuid': self._tenant_uuid,
        }


class MockLine:
    def __init__(
        self,
        id,
        name=None,
        protocol=None,
        users=None,
        context=None,
        endpoint_sip=None,
        tenant_uuid=None,
    ):
        self._id = id
        self._name = name
        self._protocol = protocol
        self._users = users or []
        self._context = context
        self._endpoint_sip = endpoint_sip
        self._tenant_uuid = tenant_uuid

    def id_(self):
        return self._id

    def users(self):
        return self._users

    def to_dict(self):
        return {
            'id': self._id,
            'name': self._name,
            'protocol': self._protocol,
            'context': self._context,
            'endpoint_sip': self._endpoint_sip,
            'tenant_uuid': self._tenant_uuid,
        }


class MockSwitchboard:
    def __init__(self, uuid, tenant_uuid=None, name=None, timeout=None):
        self._uuid = uuid
        self._tenant_uuid = tenant_uuid
        self._name = name
        self._timeout = timeout

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
            'tenant_uuid': self._tenant_uuid,
            'name': self._name,
            'timeout': self._timeout,
            'waiting_room_music_on_hold': None,
            'queue_music_on_hold': None,
        }


class MockConference:
    def __init__(self, id, name=None, extension=None, context=None, tenant_uuid=None):
        self._id = id
        self._name = name
        self._extension = extension
        self._context = context
        self._tenant_uuid = tenant_uuid

    def id(self):
        return self._id

    def to_dict(self):
        extensions = []
        if self._extension and self._context:
            extensions = [
                {
                    'context': self._context,
                    'exten': self._extension,
                }
            ]
        return {
            'id': self._id,
            'name': self._name,
            'extensions': extensions,
            'tenant_uuid': self._tenant_uuid,
        }


class MockMeeting:
    def __init__(self, uuid, name=None, tenant_uuid=None, owner_uuids=None):
        self._uuid = uuid
        self._name = name
        self._owner_uuids = owner_uuids or []
        self._tenant_uuid = tenant_uuid

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
            'name': self._name,
            'owner_uuids': self._owner_uuids,
            'tenant_uuid': self._tenant_uuid,
        }


class MockParkinglot:
    def __init__(
        self,
        id: int,
        name: str | None = None,
        slots_start: str | None = None,
        slots_end: str | None = None,
        timeout: int | None = None,
        tenant_uuid: str | None = None,
        extension: str = '500',
    ):
        self._id = id
        self._name = name or ''.join(
            choice(ascii_uppercase + digits) for _ in range(10)
        )
        self._slots_start = slots_start or str(int(extension) + 1)
        self._slots_end = slots_end or str(int(extension) + 2)
        self._timeout = timeout or 45
        self._tenant_uuid = tenant_uuid or ''
        self._extension = extension

    def id(self):
        return self._id

    def to_dict(self) -> ParkingLotSchema:
        extensions: list[ExtensionSchema] = []
        if self._extension:
            extensions = [
                {
                    'id': 1000,
                    'context': 'some-ctx',
                    'exten': self._extension,
                }
            ]

        return {
            'id': self._id,
            'tenant_uuid': self._tenant_uuid,
            'name': self._name,
            'slots_start': self._slots_start,
            'slots_end': self._slots_end,
            'timeout': self._timeout,
            'music_on_hold': 'default',
            'extensions': extensions,
        }


class MockTrunk:
    def __init__(
        self,
        id,
        endpoint_sip=None,
        endpoint_iax=None,
        endpoint_custom=None,
        tenant_uuid=None,
    ):
        self._id = id
        self._tenant_uuid = tenant_uuid
        self._endpoint_sip = endpoint_sip
        self._endpoint_iax = endpoint_iax
        self._endpoint_custom = endpoint_custom

    def id(self):
        return self._id

    def to_dict(self):
        trunk = {
            'id': self._id,
            'tenant_uuid': self._tenant_uuid,
        }
        if self._endpoint_sip:
            trunk['endpoint_sip'] = self._endpoint_sip
        if self._endpoint_iax:
            trunk['endpoint_iax'] = self._endpoint_iax
        if self._endpoint_custom:
            trunk['endpoint_custom'] = self._endpoint_custom
        return trunk


class MockVoicemail:
    def __init__(self, id, number, name, context, user_uuids=None, tenant_uuid=None):
        self._id = id
        self._number = number
        self._name = name
        self._context = context
        self._tenant_uuid = tenant_uuid
        self.user_uuids = user_uuids or []

    def id(self):
        return self._id

    def to_dict(self):
        return {
            'id': self._id,
            'number': self._number,
            'name': self._name,
            'context': self._context,
            'tenant_uuid': self._tenant_uuid,
            'users': [{"uuid": user} for user in self.user_uuids],
        }
