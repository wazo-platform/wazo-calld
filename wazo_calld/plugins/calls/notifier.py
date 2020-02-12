# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .schemas import call_schema
from .event import (
    CallAnswered,
    CallUpdated,
)

logger = logging.getLogger(__name__)


class CallNotifier:
    def __init__(self, bus):
        self._bus = bus

    def call_updated(self, call):
        call_serialized = call_schema.dump(call)
        self._bus.publish(
            CallUpdated(call_serialized),
            headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True},
        )

    def call_answered(self, call):
        call_serialized = call_schema.dump(call)
        self._bus.publish(
            CallAnswered(call_serialized),
            headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True},
        )
