# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.chat.event import ChatMessageEvent


class ChatsService(object):

    def __init__(self, bus_publisher, xivo_uuid):
        self._bus_publisher = bus_publisher
        self._xivo_uuid = xivo_uuid

    def send_message(self, request_body, user_uuid=None):
        bus_event = ChatMessageEvent(self._build_from(request_body, user_uuid),
                                     self._build_to(request_body),
                                     request_body['alias'],
                                     request_body['msg'])
        self._bus_publisher.publish(bus_event)

    def _build_from(self, request_body, token_user_uuid):
        user_uuid = token_user_uuid or str(request_body['from'])
        return (self._xivo_uuid, user_uuid)

    def _build_to(self, request_body):
        xivo_uuid = str(request_body.get('to_xivo_uuid', self._xivo_uuid))
        user_uuid = str(request_body['to'])
        return (xivo_uuid, user_uuid)
