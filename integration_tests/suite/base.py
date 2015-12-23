# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import os
import json
import logging
import requests
import time
import yaml

from hamcrest import assert_that, equal_to
from kombu import Connection
from kombu import Consumer
from kombu import Exchange
from kombu import Queue
from kombu.exceptions import TimeoutError
from requests.packages import urllib3
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

logger = logging.getLogger(__name__)

urllib3.disable_warnings()

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', 'assets')
INVALID_ACL_TOKEN = 'invalid-acl-token'
VALID_TOKEN = 'valid-token'
BUS_EXCHANGE_NAME = 'xivo'
BUS_EXCHANGE_TYPE = 'topic'
BUS_URL = 'amqp://guest:guest@localhost:5672//'
BUS_QUEUE_NAME = 'integration'
XIVO_UUID = yaml.load(open(os.path.join(ASSET_ROOT, '_common', 'etc', 'xivo-ctid-ng', 'conf.d', 'uuid.yml'), 'r'))['uuid']
STASIS_APP_NAME = 'callcontrol'


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'ctid-ng'

    @classmethod
    def get_calls_result(cls, application=None, application_instance=None, token=None):
        url = u'https://localhost:9500/1.0/calls'
        params = {}
        if application:
            params['application'] = application
            if application_instance:
                params['application_instance'] = application_instance
        result = requests.get(url,
                              params=params,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def list_calls(cls, application=None, application_instance=None, token=VALID_TOKEN):
        response = cls.get_calls_result(application, application_instance, token)
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

        return cls.post_call_raw(body, token)

    @classmethod
    def post_call_raw(cls, body, token=None):
        url = u'https://localhost:9500/1.0/calls'
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
    def put_call_user_result(cls, call_id, user_id, token):
        url = u'https://localhost:9500/1.0/calls/{call_id}/user/{user_id}'
        result = requests.put(url.format(call_id=call_id, user_id=user_id),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def connect_user(cls, call_id, user_id):
        response = cls.put_call_user_result(call_id, user_id, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    @classmethod
    def set_ari_applications(cls, *mock_applications):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'applications',
                'content': {application.name(): application.to_dict() for application in mock_applications}}
        requests.post(url, json=body)

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

    @classmethod
    def event_answer_connect(cls, from_, new_call_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "args": [
                "dialed_from",
                from_
            ],
            "channel": {
                "accountcode": "",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-16T15:13:59.526-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "",
                    "priority": 1
                },
                "id": new_call_id,
                "language": "en_US",
                "name": "SIP/my-sip-00000020",
                "state": "Up"
            },
            "timestamp": "2015-12-16T15:14:04.269-0500",
            "type": "StasisStart"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    @classmethod
    def event_hangup(cls, channel_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-18T15:40:32.439-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Ring"
            },
            "timestamp": "2015-12-18T15:40:39.073-0500",
            "type": "StasisEnd"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    @classmethod
    def event_new_channel(cls, channel_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "args": [],
            "channel": {
                "accountcode": "",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-16T15:13:59.526-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "",
                    "priority": 1
                },
                "id": channel_id,
                "language": "en_US",
                "name": "SIP/my-sip-00000020",
                "state": "Up"
            },
            "timestamp": "2015-12-16T15:14:04.269-0500",
            "type": "StasisStart"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    @classmethod
    def event_channel_updated(cls, channel_id, state='Ring'):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-18T15:40:32.439-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": state
            },
            "timestamp": "2015-12-18T15:40:39.073-0500",
            "type": "ChannelStateChange"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    @classmethod
    def listen_bus_events(cls, routing_key):
        exchange = Exchange(BUS_EXCHANGE_NAME, type=BUS_EXCHANGE_TYPE)
        with Connection(BUS_URL) as conn:
            queue = Queue(BUS_QUEUE_NAME, exchange=exchange, routing_key=routing_key, channel=conn.channel())
            queue.declare()
            queue.purge()
            cls.bus_queue = queue

    @classmethod
    def bus_events(cls):
        events = []

        def on_event(body, message):
            events.append(json.loads(body))
            message.ack()

        with Connection(BUS_URL) as conn:
            with Consumer(conn, cls.bus_queue, callbacks=[on_event]):
                try:
                    conn.drain_events(timeout=0.5)
                except TimeoutError:
                    pass

        return events

    @classmethod
    def new_call_id(cls):
        return format(time.time(), '.2f')


class MockApplication(object):

    def __init__(self, name, channels=None):
        self._name = name
        self._channels = channels or []

    def name(self):
        return self._name

    def to_dict(self):
        return {
            'name': self._name,
            'channel_ids': self._channels,
        }


class MockChannel(object):

    def __init__(self,
                 id,
                 state='Ringing',
                 creation_time='2015-01-01T00:00:00.0-0500',
                 caller_id_name='someone',
                 caller_id_number='somewhere'):
        self._id = id
        self._state = state
        self._creation_time = creation_time
        self._caller_id_name = caller_id_name
        self._caller_id_number = caller_id_number

    def id_(self):
        return self._id

    def to_dict(self):
        return {
            'id': self._id,
            'state': self._state,
            'creationtime': self._creation_time,
            'caller': {
                'name': self._caller_id_name,
                'number': self._caller_id_number
            },
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
