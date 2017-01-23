# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_bus.resources.common.event import ArbitraryEvent
from .resources import queued_call_schema

logger = logging.getLogger(__name__)


class SwitchboardsNotifier(object):

    def __init__(self, bus):
        self._bus = bus

    def queued_calls(self, switchboard_uuid, calls):
        logger.debug('Notifying updated queued calls for switchboard %s: %s calls', switchboard_uuid, len(calls))
        event = ArbitraryEvent(name='switchboard_queued_calls_updated',
                               body={'items': queued_call_schema.dump(calls, many=True).data},
                               required_acl='switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid))
        event.routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        self._bus.publish(event)
