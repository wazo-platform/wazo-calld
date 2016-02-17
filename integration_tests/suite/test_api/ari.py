# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class ARIClient(object):

    def set_applications(self, *mock_applications):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'applications',
                'content': {application.name(): application.to_dict() for application in mock_applications}}
        requests.post(url, json=body)

    def set_channels(self, *mock_channels):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'channels',
                'content': {channel.id_(): channel.to_dict() for channel in mock_channels}}
        requests.post(url, json=body)

    def set_bridges(self, *mock_bridges):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'bridges',
                'content': {bridge.id_(): bridge.to_dict() for bridge in mock_bridges}}
        requests.post(url, json=body)

    def set_originates(self, *mock_channels):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'originates',
                'content': [channel.to_dict() for channel in mock_channels]}
        requests.post(url, json=body)

    def set_channel_variable(self, variables):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'channel_variables',
                'content': variables}
        requests.post(url, json=body)

    def set_global_variables(self, variables):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'global_variables',
                'content': variables}
        requests.post(url, json=body)

    def reset(self):
        url = 'http://localhost:5039/_reset'
        requests.post(url)

    def requests(self):
        url = 'http://localhost:5039/_requests'
        return requests.get(url).json()

    def websockets(self):
        url = 'http://localhost:5039/_websockets'
        return requests.get(url).json()


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
