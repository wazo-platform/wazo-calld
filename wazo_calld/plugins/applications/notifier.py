# Copyright 2018-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .schemas import (
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

    def _build_headers_from_application(self, application):
        if 'tenant_uuid' in application:
            return {'tenant_uuid': application['tenant_uuid']}
        return None

    def call_deleted(self, application, call):
        logger.debug('Application (%s): Call (%s) deleted', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallDeleted(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def call_entered(self, application, call):
        logger.debug('Application (%s): Call (%s) entered', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallEntered(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def call_initiated(self, application, call):
        logger.debug('Application (%s): Call (%s) initialized', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallInitiated(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def call_updated(self, application, call):
        logger.debug('Application (%s): Call (%s) updated', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallUpdated(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def call_answered(self, application, call):
        logger.debug('Application (%s): Call (%s) answered', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallAnswered(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def call_progress_started(self, application, call):
        logger.debug('Application (%s): Call (%s) progress started', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallProgressStarted(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def call_progress_stopped(self, application, call):
        logger.debug('Application (%s): Call (%s) progress stopped', application['uuid'], call.id_)
        call = application_call_schema.dump(call)
        event = CallProgressStopped(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def destination_node_created(self, application, node):
        logger.debug('Application (%s): Destination node (%s) created', application['uuid'], node.uuid)
        node = application_node_schema.dump(node)
        event = DestinationNodeCreated(application['uuid'], node)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def dtmf_received(self, application, call_id, dtmf):
        logger.debug('Application (%s): DTMF (%s) received on %s', application['uuid'], dtmf, call_id)
        event = DTMFReceived(application['uuid'], call_id, dtmf)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def node_created(self, application, node):
        logger.debug('Application (%s): Node (%s) created', application['uuid'], node.uuid)
        node = application_node_schema.dump(node)
        event = NodeCreated(application['uuid'], node)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def node_deleted(self, application, node):
        logger.debug('Application (%s): Node (%s) deleted', application['uuid'], node.uuid)
        node = application_node_schema.dump(node)
        event = NodeDeleted(application['uuid'], node)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def node_updated(self, application, node):
        logger.debug('Application (%s): Node (%s) updated', application['uuid'], node.uuid)
        node = application_node_schema.dump(node)
        event = NodeUpdated(application['uuid'], node)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def playback_created(self, application, playback):
        logger.debug('Application (%s): Playback (%s) started', application['uuid'], playback['id'])
        playback = application_playback_schema.dump(playback)
        event = PlaybackCreated(application['uuid'], playback)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def playback_deleted(self, application, playback):
        logger.debug('Application (%s): Playback (%s) deleted', application['uuid'], playback['id'])
        playback = application_playback_schema.dump(playback)
        event = PlaybackDeleted(application['uuid'], playback)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def snoop_created(self, application, snoop):
        logger.debug('Application (%s): Snoop (%s) created', application['uuid'], snoop.uuid)
        snoop = application_snoop_schema.dump(snoop)
        event = SnoopCreated(application['uuid'], snoop)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def snoop_deleted(self, application, snoop_uuid):
        logger.debug('Application (%s): Snoop (%s) deleted', application['uuid'], snoop_uuid)
        snoop = {'uuid': snoop_uuid}
        event = SnoopDeleted(application['uuid'], snoop)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def snoop_updated(self, application, snoop):
        logger.debug('Application (%s): Snoop (%s) updated', application['uuid'], snoop.uuid)
        snoop = application_snoop_schema.dump(snoop)
        event = SnoopUpdated(application['uuid'], snoop)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)

    def user_outgoing_call_created(self, application, call):
        logger.debug(
            'Application (%s): User outgoing call (%s) created',
            application['uuid'], call.id_,
        )
        call = application_call_schema.dump(call)
        event = UserOutgoingCallCreated(application['uuid'], call)
        headers = self._build_headers_from_application(application)
        self._bus.publish(event, headers=headers)
