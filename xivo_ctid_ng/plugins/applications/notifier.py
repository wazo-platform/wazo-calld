# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from .schema import (
    application_call_schema,
)
from .events import (
    CallEntered,
)

logger = logging.getLogger(__name__)


class ApplicationNotifier(object):

    def __init__(self, bus):
        self._bus = bus

    def call_entered(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) entered', application_uuid, call.id_)
        call = application_call_schema.dump(call).data
        event = CallEntered(application_uuid, call)
        self._bus.publish(event)
