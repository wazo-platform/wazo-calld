# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .confd import Application
from .exceptions import (
    NoSuchApplication,
)


class ApplicationService(object):

    def __init__(self, ari, confd, amid, notifier):
        self._ari = ari
        self._confd = confd
        self._amid = amid
        self._notifier = notifier

    def get_application(self, application_uuid):
        if not Application(application_uuid, self._confd).exists():
            raise NoSuchApplication(application_uuid)

        return {'destination_node_uuid': application_uuid}
