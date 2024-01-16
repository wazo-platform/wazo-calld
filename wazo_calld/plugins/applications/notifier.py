# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_bus.resources.calls.application import (
    ApplicationCallAnsweredEvent,
    ApplicationCallDeletedEvent,
    ApplicationCallDTMFReceivedEvent,
    ApplicationCallEnteredEvent,
    ApplicationCallInitiatedEvent,
    ApplicationCallProgressStartedEvent,
    ApplicationCallProgressStoppedEvent,
    ApplicationCallUpdatedEvent,
    ApplicationDestinationNodeCreatedEvent,
    ApplicationNodeCreatedEvent,
    ApplicationNodeDeletedEvent,
    ApplicationNodeUpdatedEvent,
    ApplicationPlaybackCreatedEvent,
    ApplicationPlaybackDeletedEvent,
    ApplicationSnoopCreatedEvent,
    ApplicationSnoopDeletedEvent,
    ApplicationSnoopUpdatedEvent,
    ApplicationUserOutgoingCallCreatedEvent,
)

from .schemas import (
    application_call_schema,
    application_node_schema,
    application_playback_schema,
    application_snoop_schema,
)


logger = logging.getLogger(__name__)


class ApplicationNotifier:
    def __init__(self, bus):
        self._bus = bus

    def call_deleted(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) deleted', application['uuid'], call.id_
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallDeletedEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def call_entered(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) entered', application['uuid'], call.id_
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallEnteredEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def call_initiated(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) initialized', application['uuid'], call.id_
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallInitiatedEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def call_updated(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) updated', application['uuid'], call.id_
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallUpdatedEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def call_answered(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) answered', application['uuid'], call.id_
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallAnsweredEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def call_progress_started(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) progress started',
            application['uuid'],
            call.id_,
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallProgressStartedEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def call_progress_stopped(self, application, call):
        logger.debug(
            'Application (%s): Call (%s) progress stopped',
            application['uuid'],
            call.id_,
        )
        call = application_call_schema.dump(call)
        event = ApplicationCallProgressStoppedEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)

    def destination_node_created(self, application, node):
        logger.debug(
            'Application (%s): Destination node (%s) created',
            application['uuid'],
            node.uuid,
        )
        node = application_node_schema.dump(node)
        event = ApplicationDestinationNodeCreatedEvent(
            node, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def dtmf_received(self, application, call_id, dtmf):
        logger.debug(
            'Application (%s): DTMF (%s) received on %s',
            application['uuid'],
            dtmf,
            call_id,
        )
        event = ApplicationCallDTMFReceivedEvent(
            call_id, dtmf, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def node_created(self, application, node):
        logger.debug(
            'Application (%s): Node (%s) created', application['uuid'], node.uuid
        )
        node = application_node_schema.dump(node)
        event = ApplicationNodeCreatedEvent(
            node, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def node_deleted(self, application, node):
        logger.debug(
            'Application (%s): Node (%s) deleted', application['uuid'], node.uuid
        )
        node = application_node_schema.dump(node)
        event = ApplicationNodeDeletedEvent(
            node, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def node_updated(self, application, node):
        logger.debug(
            'Application (%s): Node (%s) updated', application['uuid'], node.uuid
        )
        node = application_node_schema.dump(node)
        event = ApplicationNodeUpdatedEvent(
            node, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def playback_created(self, application, playback):
        logger.debug(
            'Application (%s): Playback (%s) started',
            application['uuid'],
            playback['id'],
        )
        playback = application_playback_schema.dump(playback)
        event = ApplicationPlaybackCreatedEvent(
            playback, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def playback_deleted(self, application, playback):
        logger.debug(
            'Application (%s): Playback (%s) deleted',
            application['uuid'],
            playback['id'],
        )
        playback = application_playback_schema.dump(playback)
        event = ApplicationPlaybackDeletedEvent(
            playback, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def snoop_created(self, application, snoop):
        logger.debug(
            'Application (%s): Snoop (%s) created', application['uuid'], snoop.uuid
        )
        snoop = application_snoop_schema.dump(snoop)
        event = ApplicationSnoopCreatedEvent(
            snoop, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def snoop_deleted(self, application, snoop_uuid):
        logger.debug(
            'Application (%s): Snoop (%s) deleted', application['uuid'], snoop_uuid
        )
        snoop = {'uuid': snoop_uuid}
        event = ApplicationSnoopDeletedEvent(
            snoop, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def snoop_updated(self, application, snoop):
        logger.debug(
            'Application (%s): Snoop (%s) updated', application['uuid'], snoop.uuid
        )
        snoop = application_snoop_schema.dump(snoop)
        event = ApplicationSnoopUpdatedEvent(
            snoop, application['uuid'], application['tenant_uuid']
        )
        self._bus.publish(event)

    def user_outgoing_call_created(self, application, call):
        logger.debug(
            'Application (%s): User outgoing call (%s) created',
            application['uuid'],
            call.id_,
        )
        call = application_call_schema.dump(call)
        logger.debug('call %s', call)
        event = ApplicationUserOutgoingCallCreatedEvent(
            call, application['uuid'], application['tenant_uuid'], call['user_uuid']
        )
        self._bus.publish(event)
