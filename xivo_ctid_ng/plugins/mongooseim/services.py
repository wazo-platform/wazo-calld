# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.chat.event import ChatMessageEvent


class MessageCallbackService(object):

    def __init__(self, bus_publisher, xivo_uuid):
        self._bus_publisher = bus_publisher
        self._xivo_uuid = xivo_uuid

    def send_message(self, request_body, user_uuid=None):
        # TODO retrieve to_xivo_uuid and alias from /chat
        to_xivo_uuid = self._xivo_uuid
        alias = 'GhostBuster'
        bus_event = ChatMessageEvent((self._xivo_uuid, request_body['author']),
                                     (to_xivo_uuid, request_body['receiver']),
                                     alias,
                                     request_body['message'])
        self._bus_publisher.publish(bus_event)
