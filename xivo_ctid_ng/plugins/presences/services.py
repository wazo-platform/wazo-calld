# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.cti.event import UserStatusUpdateEvent

from contextlib import contextmanager
from xivo_ctid_client import Client as CtidClient


@contextmanager
def new_ctid_client(config):
    yield CtidClient(**config)


class PresencesService(object):

    def __init__(self, bus_publisher, ctid_config):
        self._bus_publisher = bus_publisher
        self._config_ctid = ctid_config

    def get_presence(self, user_uuid):
        with new_ctid_client(self._ctid_config) as ctid:
            return ctid.users.get(user_uuid)

        return '', 404

    def update_presence(self, user_uuid, request_body):
        bus_event = UserStatusUpdateEvent(user_uuid, request_body['status_name'])
        self._bus_publisher.publish(bus_event)
