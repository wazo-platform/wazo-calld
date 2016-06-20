# -*- coding: utf-8 -*-
# Copyright 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import uuid


class PresenceMessage(object):

    def __init__(self, status_name, user_uuid=None):
        self.user_uuid = user_uuid or new_uuid_str()
        self.status_name = status_name

    def as_presence_body(self):
        body = self.as_user_presence_body()
        body['user_uuid'] = self.user_uuid
        return body

    def as_user_presence_body(self):
        body = {
            'status_name': self.status_name
        }
        return body


def new_uuid_str():
    return str(uuid.uuid4())


def new_presence_message():
    return PresenceMessage('available', new_uuid_str())


def new_user_presence_message():
    return PresenceMessage('available')
