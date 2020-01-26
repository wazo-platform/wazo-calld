# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .schemas import (
    call_schema,
)
from .event import (
    CallUpdated,
)

logger = logging.getLogger(__name__)


class CallNotifier:

    def __init__(self, bus):
        self._bus = bus

    def call_updated(self, call):
        logger.debug('Call (%s) updated', call.id_)
        call_serialized = call_schema.dump(call)
        event = CallUpdated(call_serialized)
        self._bus.publish(event)
