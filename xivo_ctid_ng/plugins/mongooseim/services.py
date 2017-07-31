# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.chat.event import ChatMessageEvent
from xivo_ctid_ng.plugins.chats.services import chat_contexts


class MessageCallbackService(object):

    def __init__(self, bus_publisher, xivo_uuid):
        self._bus_publisher = bus_publisher
        self._xivo_uuid = xivo_uuid

    def send_message(self, request_body, user_uuid=None):
        from_ = request_body['author']
        to = request_body['receiver']
        key = '{}-{}'.format(from_, to)
        context = chat_contexts.get(key, {})
        to_xivo_uuid = context.get('to_xivo_uuid', self._xivo_uuid)
        alias = context.get('alias', to)

        bus_event = ChatMessageEvent((self._xivo_uuid, from_),
                                     (to_xivo_uuid, to),
                                     alias,
                                     request_body['message'])
        self._bus_publisher.publish(bus_event)
