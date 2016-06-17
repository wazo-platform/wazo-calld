# -*- coding: utf-8 -*-
# Copyright 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import uuid


class ChatMessage(object):

    def __init__(self, alias, content, to, from_=None):
        self.alias = alias
        self.content = content
        self.to = to
        self.to_xivo_uuid = None
        self.from_ = from_

    def as_chat_body(self):
        body = self.as_user_chat_body()
        body['from'] = self.from_
        return body

    def as_user_chat_body(self):
        body = {
            'alias': self.alias,
            'to': self.to,
            'msg': self.content,
        }
        if self.to_xivo_uuid is not None:
            body['to_xivo_uuid'] = self.to_xivo_uuid
        return body


def new_uuid_str():
    return str(uuid.uuid4())


def new_chat_message():
    return ChatMessage('alice', 'lorem ipsum',
                       to=new_uuid_str(), from_=new_uuid_str())


def new_user_chat_message():
    return ChatMessage('alice', 'lorem ipsum',
                       to=new_uuid_str())
