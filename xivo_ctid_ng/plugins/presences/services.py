# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.cti.event import UserStatusUpdateEvent

import requests

from .exceptions import NoSuchUser, NoSuchLine, XiVOCtidUnreachable


def _is_404(exception):
    response = getattr(exception, 'response')
    status_code = getattr(response, 'status_code')
    return status_code == 404


class UserPresencesService(object):

    def __init__(self, bus_publisher, ctid_client, ctid_config, local_xivo_uuid):
        self._bus_publisher = bus_publisher
        self._ctid_client = ctid_client
        self._ctid_config = ctid_config
        self._xivo_uuid = local_xivo_uuid

    def get_local_presence(self, user_uuid):
        try:
            response = self._ctid_client.users.get(user_uuid)
            return response['origin_uuid'], response['presence']
        except requests.RequestException as e:
            if _is_404(e):
                raise NoSuchUser(user_uuid)
            raise XiVOCtidUnreachable(self._ctid_config, e)

    def get_remote_presence(self, xivo_uuid, user_uuid):
        return

    def get_presence(self, xivo_uuid, user_uuid):
        if xivo_uuid in [None, self._xivo_uuid]:
            return self.get_local_presence(user_uuid)
        else:
            return self.get_remote_presence(xivo_uuid, user_uuid)

    def update_presence(self, user_uuid, status):
        bus_event = UserStatusUpdateEvent(user_uuid, status)
        self._bus_publisher.publish(bus_event)


class LinePresencesService(object):

    def __init__(self, ctid_client, ctid_config):
        self._ctid_client = ctid_client
        self._ctid_config = ctid_config

    def get_presence(self, line_id):
        try:
            response = self._ctid_client.endpoints.get(line_id)
            return response['id'], response['origin_uuid'], response['status']
        except requests.RequestException as e:
            if _is_404(e):
                raise NoSuchLine(line_id)
            raise XiVOCtidUnreachable(self._ctid_config, e)
