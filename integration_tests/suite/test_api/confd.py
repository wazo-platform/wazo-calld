# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class ConfdClient(object):

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        return 'https://{host}:{port}/{path}'.format(host=self._host,
                                                     port=self._port,
                                                     path='/'.join(parts))

    def set_users(self, *mock_users):
        url = self.url('_set_response')
        body = {'response': 'users',
                'content': {user.uuid(): user.to_dict() for user in mock_users}}
        requests.post(url, json=body, verify=False)

    def set_lines(self, *mock_lines):
        url = self.url('_set_response')
        body = {'response': 'lines',
                'content': {line.id_(): line.to_dict() for line in mock_lines}}
        requests.post(url, json=body, verify=False)

    def set_user_lines(self, set_user_lines):
        content = {}
        for user, user_lines in set_user_lines.iteritems():
            content[user] = [user_line.to_dict() for user_line in user_lines]

        url = self.url('_set_response')
        body = {'response': 'user_lines',
                'content': content}
        requests.post(url, json=body, verify=False)

    def reset(self):
        url = self.url('_reset')
        requests.post(url, verify=False)


class MockUser(object):

    def __init__(self, uuid):
        self._uuid = uuid

    def uuid(self):
        return self._uuid

    def to_dict(self):
        return {
            'uuid': self._uuid,
        }


class MockLine(object):

    def __init__(self, id, name=None, protocol=None, users=None, context=None):
        self._id = id
        self._name = name
        self._protocol = protocol
        self._users = users or []
        self._context = context

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
        }


class MockUserLine(object):

    def __init__(self, line_id, main_line=True):
        self._line_id = line_id
        self._main_line = main_line

    def to_dict(self):
        return {
            'user_id': None,
            'line_id': self._line_id,
            'main_line': self._main_line
        }
