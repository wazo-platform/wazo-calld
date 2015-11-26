# -*- coding: utf-8 -*-

# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import logging
import requests

from collections import defaultdict
from hamcrest import assert_that, equal_to
from requests.packages import urllib3
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

logger = logging.getLogger(__name__)

urllib3.disable_warnings()

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', 'assets')
VALID_TOKEN = 'valid-token'


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'ctid-ng'

    @classmethod
    def get_calls_result(cls, token=None):
        url = u'https://localhost:9500/1.0/calls'
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def list_calls(cls, token=VALID_TOKEN):
        response = cls.get_calls_result(token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    @classmethod
    def get_call_result(cls, call_id, token=None):
        url = u'https://localhost:9500/1.0/calls/{call_id}'
        result = requests.get(url.format(call_id=call_id),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def get_call(cls, call_id, token=VALID_TOKEN):
        response = cls.get_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    @classmethod
    def post_call_result(cls, source, priority, extension, context, variables=None, token=None):
        url = u'https://localhost:9500/1.0/calls'
        body = {
            'source': {
                'user': source,
            },
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }
        if variables:
            body.update({'variables': variables})
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    @classmethod
    def originate(cls, source, priority, extension, context, variables=None, token=VALID_TOKEN):
        response = cls.post_call_result(source, priority, extension, context, variables, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    @classmethod
    def delete_call_result(cls, call_id, token=None):
        url = u'https://localhost:9500/1.0/calls/{call_id}'
        result = requests.delete(url.format(call_id=call_id),
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    @classmethod
    def hangup_call(cls, call_id, token=VALID_TOKEN):
        response = cls.delete_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(204))

    @classmethod
    def get_plugins_result(cls, token=None):
        url = u'https://localhost:9500/1.0/plugins'
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def set_ari_channels(cls, *mock_channels):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'channels',
                'content': {channel.id_(): channel.to_dict() for channel in mock_channels}}
        requests.post(url, json=body)

    @classmethod
    def set_ari_bridges(cls, *mock_bridges):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'bridges',
                'content': {bridge.id_(): bridge.to_dict() for bridge in mock_bridges}}
        requests.post(url, json=body)

    @classmethod
    def set_ari_originates(cls, *mock_channels):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'originates',
                'content': [channel.to_dict() for channel in mock_channels]}
        requests.post(url, json=body)

    @classmethod
    def set_ari_channel_variable(cls, variables):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'channel_variable',
                'content': variables}
        requests.post(url, json=body)

    @classmethod
    def set_confd_users(cls, *mock_users):
        url = 'https://localhost:9486/_set_response'
        content = {}
        for user in mock_users:
            content[user.id_()] = user.to_dict()
            content[user.uuid()] = user.to_dict()
        body = {'response': 'users',
                'content': content}
        requests.post(url, json=body, verify=False)

    @classmethod
    def set_confd_lines(cls, *mock_lines):
        url = 'https://localhost:9486/_set_response'
        body = {'response': 'lines',
                'content': {line.id_(): line.to_dict() for line in mock_lines}}
        requests.post(url, json=body, verify=False)

    @classmethod
    def set_confd_user_lines(cls, set_user_lines):
        content = {}
        for user, user_lines in set_user_lines.iteritems():
            content[user] = [user_line.to_dict() for user_line in user_lines]

        url = 'https://localhost:9486/_set_response'
        body = {'response': 'user_lines',
                'content': content}
        requests.post(url, json=body, verify=False)

    @classmethod
    def reset_ari(cls):
        url = 'http://localhost:5039/_reset'
        requests.post(url)

    @classmethod
    def reset_confd(cls):
        url = 'https://localhost:9486/_reset'
        requests.post(url, verify=False)

    @classmethod
    def ari_requests(cls):
        url = 'http://localhost:5039/_requests'
        return requests.get(url).json()


class MockChannel(object):

    def __init__(self, id, state='Ringing', creation_time='2015-01-01T00:00:00.0-0500'):
        self._id = id
        self._state = state
        self._creation_time = creation_time

    def id_(self):
        return self._id

    def to_dict(self):
        return {
            'id': self._id,
            'state': self._state,
            'creationtime': self._creation_time
        }


class MockBridge(object):

    def __init__(self, id, channels=None):
        self._id = id
        self._channels = channels or []

    def id_(self):
        return self._id

    def to_dict(self):
        return {
            'id': self._id,
            'channels': self._channels
        }


class MockUser(object):

    def __init__(self, id, uuid=None):
        self._id = id
        self._uuid = uuid

    def id_(self):
        return self._id

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'id': self._id,
            'uuid': self._uuid,
        }


class MockLine(object):

    def __init__(self, id, name=None, protocol=None, users=None):
        self._id = id
        self._name = name
        self._protocol = protocol
        self._users = users or []

    def id_(self):
        return self._id

    def users(self):
        return self._users

    def to_dict(self):
        return {
            'id': self._id,
            'name': self._name,
            'protocol': self._protocol,
        }


class MockUserLine(object):

    def __init__(self, user_id, line_id, main_line=True):
        self._user_id = user_id
        self._line_id = line_id
        self._main_line = main_line

    def user_id(self):
        return self._user_id

    def to_dict(self):
        return {
            'user_id': self._user_id,
            'line_id': self._line_id,
            'main_line': self._main_line
        }
