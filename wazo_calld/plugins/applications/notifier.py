# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .schema import (
    application_call_schema,
    application_node_schema,
    application_playback_schema,
    application_snoop_schema,
)
from .events import (
    CallAnswered,
    CallDeleted,
    CallEntered,
    CallInitiated,
    CallProgressStarted,
    CallProgressStopped,
    CallUpdated,
    DestinationNodeCreated,
    DTMFReceived,
    NodeCreated,
    NodeDeleted,
    NodeUpdated,
    PlaybackCreated,
    PlaybackDeleted,
    SnoopCreated,
    SnoopDeleted,
    SnoopUpdated,
    UserOutgoingCallCreated,
)

logger = logging.getLogger(__name__)


class ApplicationNotifier:

    def __init__(self, bus):
        self._bus = bus

    def call_deleted(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) deleted', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallDeleted(application_uuid, call)
        self._bus.publish(event)

    def call_entered(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) entered', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallEntered(application_uuid, call)
        self._bus.publish(event)

    def call_initiated(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) initialized', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallInitiated(application_uuid, call)
        self._bus.publish(event)

    def call_updated(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) updated', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallUpdated(application_uuid, call)
        self._bus.publish(event)

    def call_answered(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) answered', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallAnswered(application_uuid, call)
        self._bus.publish(event)

    def call_progress_started(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) progress started', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallProgressStarted(application_uuid, call)
        self._bus.publish(event)

    def call_progress_stopped(self, application_uuid, call):
        logger.debug('Application (%s): Call (%s) progress stopped', application_uuid, call.id_)
        call = application_call_schema.dump(call)
        event = CallProgressStopped(application_uuid, call)
        self._bus.publish(event)

    def destination_node_created(self, application_uuid, node):
        logger.debug('Application (%s): Destination node (%s) created', application_uuid, node.uuid)
        node = application_node_schema.dump(node)
        event = DestinationNodeCreated(application_uuid, node)
        self._bus.publish(event)

    def dtmf_received(self, application_uuid, call_id, dtmf):
        logger.debug('Application (%s): DTMF (%s) received on %s', application_uuid, dtmf, call_id)
        event = DTMFReceived(application_uuid, call_id, dtmf)
        self._bus.publish(event)

    def node_created(self, application_uuid, node):
        logger.debug('Application (%s): Node (%s) created', application_uuid, node.uuid)
        node = application_node_schema.dump(node)
        event = NodeCreated(application_uuid, node)
        self._bus.publish(event)

    def node_deleted(self, application_uuid, node):
        logger.debug('Application (%s): Node (%s) deleted', application_uuid, node.uuid)
        node = application_node_schema.dump(node)
        event = NodeDeleted(application_uuid, node)
        self._bus.publish(event)

    def node_updated(self, application_uuid, node):
        logger.debug('Application (%s): Node (%s) updated', application_uuid, node.uuid)
        node = application_node_schema.dump(node)
        event = NodeUpdated(application_uuid, node)
        self._bus.publish(event)

    def playback_created(self, application_uuid, playback):
        logger.debug('Application (%s): Playback (%s) started', application_uuid, playback['id'])
        playback = application_playback_schema.dump(playback)
        event = PlaybackCreated(application_uuid, playback)
        self._bus.publish(event)

    def playback_deleted(self, application_uuid, playback):
        logger.debug('Application (%s): Playback (%s) deleted', application_uuid, playback['id'])
        playback = application_playback_schema.dump(playback)
        event = PlaybackDeleted(application_uuid, playback)
        self._bus.publish(event)

    def snoop_created(self, application_uuid, snoop):
        logger.debug('Application (%s): Snoop (%s) created', application_uuid, snoop.uuid)
        snoop = application_snoop_schema.dump(snoop)
        event = SnoopCreated(application_uuid, snoop)
        self._bus.publish(event)

    def snoop_deleted(self, application_uuid, snoop_uuid):
        logger.debug('Application (%s): Snoop (%s) deleted', application_uuid, snoop_uuid)
        snoop = {'uuid': snoop_uuid}
        event = SnoopDeleted(application_uuid, snoop)
        self._bus.publish(event)

    def snoop_updated(self, application_uuid, snoop):
        logger.debug('Application (%s): Snoop (%s) updated', application_uuid, snoop.uuid)
        snoop = application_snoop_schema.dump(snoop)
        event = SnoopUpdated(application_uuid, snoop)
        self._bus.publish(event)

    def user_outgoing_call_created(self, application_uuid, call):
        logger.debug(
            'Application (%s): User outgoing call (%s) created',
            application_uuid, call.id_,
        )
        call = application_call_schema.dump(call)
        event = UserOutgoingCallCreated(application_uuid, call)
        self._bus.publish(event)
