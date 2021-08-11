# Copyright 2015-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class ConfdClient:

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        return 'http://{host}:{port}/{path}'.format(
            host=self._host,
            port=self._port,
            path='/'.join(parts)
        )

    def is_up(self):
        url = self.url()
        try:
            response = requests.get(url)
            return response.status_code == 404
        except requests.RequestException:
            return False

    def set_applications(self, *mock_applications):
        url = self.url('_set_response')
        body = {'response': 'applications',
                'content': {app.uuid(): app.to_dict() for app in mock_applications}}

        requests.post(url, json=body)

    def set_users(self, *mock_users):
        url = self.url('_set_response')
        body = {'response': 'users',
                'content': {user.uuid(): user.to_dict() for user in mock_users}}
        requests.post(url, json=body)

    def set_lines(self, *mock_lines):
        url = self.url('_set_response')
        body = {'response': 'lines',
                'content': {line.id_(): line.to_dict() for line in mock_lines}}
        requests.post(url, json=body)

    def set_user_lines(self, set_user_lines):
        content = {}
        for user, user_lines in set_user_lines.items():
            content[user] = [user_line.to_dict() for user_line in user_lines]

        url = self.url('_set_response')
        body = {'response': 'user_lines',
                'content': content}
        requests.post(url, json=body)

    def set_user_voicemails(self, set_user_voicemails):
        content = {}
        for user, voicemails in set_user_voicemails.items():
            content[user] = [voicemail.to_dict() for voicemail in voicemails]

        url = self.url('_set_response')
        body = {'response': 'user_voicemails',
                'content': content}
        requests.post(url, json=body)

    def set_switchboards(self, *mock_switchboards):
        url = self.url('_set_response')
        body = {'response': 'switchboards',
                'content': {switchboard.uuid(): switchboard.to_dict() for switchboard in mock_switchboards}}

        requests.post(url, json=body)

    def set_switchboard_fallbacks(self, *mock_switchboard_fallbacks):
        url = self.url('_set_response')
        body = {'response': 'switchboard_fallbacks',
                'content': {
                    switchboard_fallback.uuid(): switchboard_fallback.to_dict()
                    for switchboard_fallback in mock_switchboard_fallbacks
                }}

        requests.post(url, json=body)

    def set_conferences(self, *mock_conferences):
        url = self.url('_set_response')
        body = {'response': 'conferences',
                'content': {conference.id(): conference.to_dict() for conference in mock_conferences}}

        requests.post(url, json=body)

    def set_moh(self, *mock_mohs):
        url = self.url('_set_response')
        body = {'response': 'moh',
                'content': {moh.uuid(): moh.to_dict() for moh in mock_mohs}}

        requests.post(url, json=body)

    def set_trunks(self, *mock_trunks):
        url = self.url('_set_response')
        body = {
            'response': 'trunks',
            'content': {trunk.id(): trunk.to_dict() for trunk in mock_trunks},
        }

        requests.post(url, json=body)

    def set_voicemails(self, *mock_voicemails):
        url = self.url('_set_response')
        body = {'response': 'voicemails',
                'content': {voicemail.id(): voicemail.to_dict() for voicemail in mock_voicemails}}
        requests.post(url, json=body)

    def reset(self):
        url = self.url('_reset')
        requests.post(url)

    def requests(self):
        url = self.url('_requests')
        return requests.get(url).json()


class MockApplication:

    def __init__(self, uuid, name, destination=None, type_=None, moh=None, answer=None):
        self._uuid = uuid
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

    def __init__(self, uuid, line_ids=None, mobile=None, voicemail=None):
        self._uuid = uuid
        self._line_ids = line_ids or []
        self._mobile = mobile
        self._voicemail = voicemail

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
            'lines': [{'id': line_id} for line_id in self._line_ids],
            'mobile_phone_number': self._mobile,
            'voicemail': self._voicemail,
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


class MockSwitchboardFallback:

    def __init__(self, uuid, noanswer_destination=None):
        self._uuid = uuid
        self._noanswer_destination = noanswer_destination

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'noanswer_destination': self._noanswer_destination,
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


class MockTrunk:
    def __init__(
            self, id, endpoint_sip=None, endpoint_iax=None, endpoint_custom=None, tenant_uuid=None
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
            'users': [
                {"uuid": user} for user in self.user_uuids
            ]
        }
