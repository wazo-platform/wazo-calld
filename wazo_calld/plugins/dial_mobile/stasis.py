# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wazo_calld.ari_ import CoreARI

    from .services import DialMobileService

logger = logging.getLogger(__name__)


class DialMobileStasis:
    _app_name = 'dial_mobile'

    def __init__(self, ari: CoreARI, service: DialMobileService):
        self._core_ari = ari
        self._ari = ari.client
        self._service = service

    def stasis_start(self, event_object, event):
        if event['application'] != self._app_name:
            return

        args = event['args']
        channel_id = event['channel']['id']
        logger.debug(
            'Channel id %s (%s) entered app %s with args %s',
            channel_id,
            event['channel']['name'],
            self._app_name,
            args,
        )

        match args:
            case ['dial', aor]:
                origin_channel_id = event['channel']['channelvars']['CHANNEL(linkedid)']
                self._service.dial_all_contacts(channel_id, origin_channel_id, aor)
            case ['join', future_bridge_uuid]:
                self._service.join_bridge(channel_id, future_bridge_uuid)
            case ['pickup', exten, context]:
                future_bridge_uuid = self._service.find_bridge_by_exten_context(
                    exten, context
                )
                if future_bridge_uuid:
                    self._service.join_bridge(channel_id, future_bridge_uuid)
                else:
                    logger.debug('no matching mobile pickup found')
                    self._ari.channels.continueInDialplan(channelId=channel_id)
            case _:
                logger.info(
                    '%s called with unknown or insufficient arguments %s',
                    self._app_name,
                    args,
                )

    def on_channel_left_bridge(self, channel, event):
        if event['application'] != self._app_name:
            return

        bridge_id = event['bridge']['id']

        self._service.clean_bridge(bridge_id)

    def _add_ari_application(self):
        self._core_ari.register_application(self._app_name)

    def channel_destroyed(self, channel, event):
        self._service.notify_channel_gone(event['channel']['id'])

    _DIALABLE_CONTACT_STATUSES = frozenset({'Created', 'NonQualified', 'Reachable'})

    def on_contact_status_change(self, event_object, event):
        if event.get('application') != self._app_name:
            return
        contact_info = event.get('contact_info') or {}
        if contact_info.get('contact_status') not in self._DIALABLE_CONTACT_STATUSES:
            return
        aor = contact_info.get('aor')
        if not aor:
            return
        self._service.notify_contact_available(aor)

    def _subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('ChannelLeftBridge', self.on_channel_left_bridge)
        self._ari.on_channel_event('ChannelDestroyed', self.channel_destroyed)
        self._ari.on_endpoint_event(
            'ContactStatusChange', self.on_contact_status_change
        )
        self._ari.on_application_registered(
            self._app_name, self.subscribe_to_pjsip_endpoint_events
        )
        self._ari.on_application_deregistered(
            self._app_name, self.unsubscribe_from_pjsip_endpoint_events
        )

    def subscribe_to_pjsip_endpoint_events(self):
        # Subscribing to the endpoint event source is required for
        # `ContactStatusChange` events to be delivered to the dial_mobile
        # application; otherwise only channel-scoped events flow.
        self._ari.applications.subscribe(
            applicationName=self._app_name, eventSource='endpoint:PJSIP'
        )

    def unsubscribe_from_pjsip_endpoint_events(self):
        self._ari.applications.unsubscribe(
            applicationName=self._app_name, eventSource='endpoint:PJSIP'
        )

    def initialize(self):
        self._subscribe()
        self._add_ari_application()
