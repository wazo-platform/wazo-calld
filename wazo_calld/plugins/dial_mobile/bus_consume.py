# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound

logger = logging.getLogger(__name__)


class EventHandler:

    def __init__(self, service):
        self._service = service

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe('BridgeEnter', self._on_bridge_enter)
        bus_consumer.subscribe('DialEnd', self._on_dial_end)
        bus_consumer.subscribe('UserEvent', self._on_user_event)
        bus_consumer.subscribe('auth_refresh_token_created', self._on_refresh_token_created)
        bus_consumer.subscribe('auth_refresh_token_deleted', self._on_refresh_token_deleted)

    def _on_user_event(self, event):
        if event['UserEvent'] != 'Pushmobile':
            return

        user_uuid = event['WAZO_DST_UUID']
        video_enabled = event['WAZO_VIDEO_ENABLED'] == '1'
        tenant_uuid = event.get('ChanVariable', {}).get('WAZO_TENANT_UUID')

        logger.info(
            'Received push notification request for user %s from %s <%s>',
            user_uuid, event["CallerIDName"], event["CallerIDNum"],
        )

        self._service.send_push_notification(
            tenant_uuid,
            user_uuid,
            event["Uniqueid"],
            event['ChanVariable']['WAZO_SIP_CALL_ID'],
            event["CallerIDName"],
            event["CallerIDNum"],
            video_enabled,
        )

    def _on_refresh_token_created(self, event):
        if not event['mobile']:
            return

        self._service.on_mobile_refresh_token_created(event['user_uuid'])

    def _on_refresh_token_deleted(self, event):
        if not event['mobile']:
            return

        self._service.on_mobile_refresh_token_deleted(event['user_uuid'])

    def _on_bridge_enter(self, event):
        # Ignoring unrelated bridges
        if event['BridgeType'] != 'stasis':
            return

        if not event['BridgeUniqueid'].startswith('wazo-dial-mobile-'):
            return

        protocol, end = event['Channel'].split('/', 1)
        if protocol != 'PJSIP':
            # Mobiles can only be PJSIP
            return

        endpoint, _ = end.split('-', 1)
        linkedid = event['Linkedid']
        user_uuid = event['ChanVariable']['XIVO_USERUUID']

        try:
            is_answered_by_mobile_endpoint = self._service.is_push_answered_by_mobile(
                linkedid,
                event['Uniqueid'],
                endpoint,
                user_uuid,
            )
        except ARINotFound:
            # The channel that entered the bridge has already been hung up
            return self._service.cancel_push_mobile(linkedid)

        if is_answered_by_mobile_endpoint:
            self._service.remove_pending_push_mobile(linkedid)
        else:
            self._service.cancel_push_mobile(linkedid)

    def _on_dial_end(self, event):
        # Ignore dial_end if it's in an unrelated context
        if event['DestContext'] != 'wazo_wait_for_registration':
            return

        # Ignore dial_end if the call was answered, those are handled in _on_bridge_enter
        if event['DialStatus'] == 'ANSWER':
            return

        self._service.cancel_push_mobile(event['Uniqueid'])
