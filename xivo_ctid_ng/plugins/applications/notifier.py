# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from .schema import (
    application_call_schema,
    application_node_schema,
)
from .events import (
    CallDeleted,
    CallEntered,
    CallInitiated,
    CallUpdated,
    DestinationNodeCreated,
    NodeCreated,
    NodeDeleted,
    NodeUpdated,
)

logger = logging.getLogger(__name__)


class ApplicationNotifier(object):

    def __init__(self, bus):
        self._bus = bus

    def call_deleted(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) deleted', application_uuid, call.id_)
        call = application_call_schema.dump(call).data
        event = CallDeleted(application_uuid, call)
        self._bus.publish(event)

    def call_entered(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) entered', application_uuid, call.id_)
        call = application_call_schema.dump(call).data
        event = CallEntered(application_uuid, call)
        self._bus.publish(event)

    def call_initiated(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) initialized', application_uuid, call.id_)
        call = application_call_schema.dump(call).data
        event = CallInitiated(application_uuid, call)
        self._bus.publish(event)

    def call_updated(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) updated', application_uuid, call.id_)
        call = application_call_schema.dump(call).data
        event = CallUpdated(application_uuid, call)
        self._bus.publish(event)

    def destination_node_created(self, application_uuid, node):
        logger.debug('Application (%s): Destination node (%s) created', application_uuid, node.uuid)
        node = application_node_schema.dump(node).data
        event = DestinationNodeCreated(application_uuid, node)
        self._bus.publish(event)

    def node_created(self, application_uuid, node):
        logger.debug('Application (%s): Node (%s) created', application_uuid, node.uuid)
        node = application_node_schema.dump(node).data
        event = NodeCreated(application_uuid, node)
        self._bus.publish(event)

    def node_deleted(self, application_uuid, node):
        logger.debug('Application (%s): Node (%s) deleted', application_uuid, node.uuid)
        node = application_node_schema.dump(node).data
        event = NodeDeleted(application_uuid, node)
        self._bus.publish(event)

    def node_updated(self, application_uuid, node):
        logger.debug('Application (%s): Node (%s) updated', application_uuid, node.uuid)
        node = application_node_schema.dump(node).data
        event = NodeUpdated(application_uuid, node)
        self._bus.publish(event)
