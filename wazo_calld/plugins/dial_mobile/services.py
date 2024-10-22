# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
import time
import uuid
from collections import namedtuple

import requests
from ari.exceptions import ARINotFound

from wazo_calld.plugin_helpers.ari_ import Bridge

logger = logging.getLogger(__name__)

PendingPushMobile = namedtuple(
    'PendingPushMobile', ['call_id', 'tenant_uuid', 'user_uuid', 'payload']
)


class _NoSuchChannel(Exception):
    pass


class _PollingContactDialer:
    def __init__(
        self, ari, future_bridge_uuid, channel_id, aor, ringing_time, pickup_mark
    ):
        self._ari = ari
        self.future_bridge_uuid = future_bridge_uuid
        self.should_stop = threading.Event()
        self._thread = threading.Thread(
            name='PollingContactDialer',
            target=self._run_no_exception,
            args=(channel_id, aor),
        )
        self._called_contacts = set()
        self.is_running = False
        self._dialed_channels = set()
        self._caller_channel_id = channel_id
        self._ringing_time = ringing_time
        self.pickup_mark = pickup_mark

        dialer_id = str(self)

        class CustomAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                return f'{dialer_id}: {msg}', kwargs

        self.logger = CustomAdapter(logging.getLogger(__name__), {})

    def __str__(self) -> str:
        return f'Dialer({self.future_bridge_uuid}, {self._caller_channel_id})'

    def start(self):
        self.logger.debug('Starting')
        self._thread.start()

    def stop(self):
        if not self._thread.is_alive():
            return

        self.logger.debug('Stopping')
        self.should_stop.set()
        self._thread.join()
        self.logger.debug('Stopped')

    def _run_no_exception(self, *args, **kwargs):
        try:
            return self._run(*args, **kwargs)
        except Exception:
            self.logger.exception('Unhandled exception in %s thread', self._thread.name)

    def _run(self, channel_id, aor):
        channel = self._ari.channels.get(channelId=channel_id)
        caller_id = '"{name}" <{number}>'.format(**channel.json['caller'])

        while True:
            contacts = self._get_contacts(channel_id, aor)
            for contact in contacts:
                if self.should_stop.is_set():
                    break

                self._send_contact_to_current_call(
                    contact, self.future_bridge_uuid, caller_id
                )

            if not self._channel_is_up(channel_id):
                self.logger.debug(
                    'calling channel %s is gone: stopping %s thread',
                    channel_id,
                    self._thread.name,
                )
                self.should_stop.set()
                break

            if self.should_stop.is_set():
                break

            time.sleep(0.25)

        self._remove_unanswered_channels()

    def _channel_is_up(self, channel_id):
        try:
            self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            return False
        else:
            return True

    def _send_contact_to_current_call(self, contact, future_bridge_uuid, caller_id):
        if contact in self._called_contacts:
            return

        self.logger.debug(
            'sending %s to the future bridge %s', contact, future_bridge_uuid
        )
        channel = self._ari.channels.originate(
            endpoint=contact,
            app='dial_mobile',
            appArgs=['join', future_bridge_uuid],
            callerId=caller_id,
            originator=self._caller_channel_id,
            timeout=self._ringing_time,
        )

        self.logger.debug('Dialed channel %s', channel.id)
        self._called_contacts.add(contact)
        self._dialed_channels.add(channel)

    def _remove_unanswered_channels(self):
        for channel in self._dialed_channels:
            try:
                channel_info = channel.get()
                if channel_info.json['state'] == 'Up':
                    continue
                self._ari.channels.hangup(channelId=channel.id)
            except ARINotFound:
                continue  # The channel has already been hung up

    def _get_contacts(self, channel_id, aor):
        asterisk_dialplan_function = f'PJSIP_DIAL_CONTACTS({aor})'
        try:
            response = self._ari.channels.getChannelVar(
                channelId=channel_id,
                variable=asterisk_dialplan_function,
            )
            return [contact for contact in response['value'].split('&') if contact]
        except ARINotFound:
            return []

    def _on_channel_gone(self, channel_id):
        self.logger.debug(
            'Channel gone %s, dialed %d channels',
            channel_id,
            len(self._dialed_channels),
        )
        dialed_channel_ids = {channel.id for channel in self._dialed_channels}
        if (
            channel_id not in dialed_channel_ids
            and channel_id != self._caller_channel_id
        ):
            raise _NoSuchChannel(channel_id)

        # call was refused, stop ringing and hangup
        self.logger.debug(
            'Caller or dialed channel %s is gone, stopping dialer...', channel_id
        )
        self.stop()
        if channel_id != self._caller_channel_id:
            self.logger.debug(
                'Call was refused, hanging up caller channel %s', channel_id
            )
            try:
                self._ari.channels.hangup(channelId=self._caller_channel_id)
            except ARINotFound:
                pass  # Already gone


class DialMobileService:
    def __init__(self, ari, notifier, amid_client, auth_client):
        self._ari = ari.client
        self._auth_client = auth_client
        self._amid_client = amid_client
        self._contact_dialers = {}
        self._outgoing_calls = {}
        self._call_ring_time = {}
        self._pending_push_mobile = {}
        self._notifier = notifier

    def find_bridge_by_exten_context(self, exten, context):
        pickup_mark = f'{exten}%{context}'
        for bridge_uuid, dialer in self._contact_dialers.items():
            if dialer.pickup_mark == pickup_mark:
                return bridge_uuid

    def dial_all_contacts(self, caller_channel_id, origin_channel_id, aor):
        self._ari.channels.ring(channelId=caller_channel_id)

        logger.info('dial_all_contacts(%s, %s)', caller_channel_id, aor)
        future_bridge_uuid = str(uuid.uuid4())

        logger.debug(
            '%s is waiting for a channel to join the bridge %s',
            caller_channel_id,
            future_bridge_uuid,
        )
        ringing_time = self._call_ring_time.get(origin_channel_id, 30)
        pickup_mark = self._ari.channels.getChannelVar(
            channelId=caller_channel_id, variable=f'PJSIP_ENDPOINT({aor},PICKUPMARK)'
        )['value']
        dialer = _PollingContactDialer(
            self._ari,
            future_bridge_uuid,
            caller_channel_id,
            aor,
            ringing_time,
            pickup_mark,
        )
        self._contact_dialers[future_bridge_uuid] = dialer
        self._outgoing_calls[future_bridge_uuid] = caller_channel_id
        dialer.start()

    def join_bridge(self, channel_id, future_bridge_uuid):
        logger.info('%s is joining bridge %s', channel_id, future_bridge_uuid)
        dialer = self._contact_dialers.pop(future_bridge_uuid, None)
        logger.debug('Removing dialer: %s', str(dialer))
        if not dialer:
            try:
                self._ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                # If its already gone do nothing
                pass
            self.cancel_push_mobile(channel_id)
            return

        dialer.stop()
        outgoing_channel_id = self._outgoing_calls[future_bridge_uuid]
        try:
            self._ari.channels.answer(channelId=outgoing_channel_id)
        except ARINotFound:
            logger.info(
                'the caller (%s) left the call before being bridged',
                outgoing_channel_id,
            )
            try:
                self._ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                # If its already gone do nothing
                pass
            self.cancel_push_mobile(channel_id)
            return

        try:
            self._ari.channels.answer(channelId=channel_id)
        except ARINotFound:
            logger.info(
                'the answered (%s) left the call before being bridged', channel_id
            )
            return

        bridge = self._ari.bridges.createWithId(
            type='mixing',
            bridgeId=f'wazo-dial-mobile-{future_bridge_uuid}',
        )
        # Without the inhibitConnectedLineUpdates everyone in the bridge will receive a new
        # connected line update with the caller ID of the caller when PAI is trusted, including
        # the caller...
        bridge.addChannel(channel=channel_id, inhibitConnectedLineUpdates=True)
        bridge.addChannel(channel=outgoing_channel_id, inhibitConnectedLineUpdates=True)

    def notify_channel_gone(self, channel_id):
        to_remove = set()

        for key, dialer in self._contact_dialers.items():
            try:
                dialer._on_channel_gone(channel_id)
            except _NoSuchChannel:
                continue
            else:
                to_remove.add(key)

        for key in to_remove:
            logger.debug('Removing dialer: %s', str(self._contact_dialers[key]))
            del self._contact_dialers[key]

    def clean_bridge(self, bridge_id):
        bridge_helper = Bridge(bridge_id, self._ari)
        if bridge_helper.has_lone_channel():
            logger.debug(
                'dial_mobile: bridge %s: only one participant left, hanging up',
                bridge_id,
            )
            bridge_helper.hangup_all()
        elif bridge_helper.is_empty():
            logger.debug(
                'dial_mobile bridge %s: bridge is empty, destroying', bridge_id
            )
            try:
                self._ari.bridges.destroy(bridgeId=bridge_id)
            except ARINotFound:
                pass

    def on_calld_stopping(self):
        for dialer in self._contact_dialers.values():
            dialer.stop()

    def _set_user_hint(self, user_uuid, has_mobile_sessions):
        self._amid_client.action(
            'Setvar',
            {
                'Variable': f'DEVICE_STATE(Custom:{user_uuid}-mobile)',
                'Value': 'NOT_INUSE' if has_mobile_sessions else 'UNAVAILABLE',
            },
        )

    def on_mobile_refresh_token_created(self, user_uuid):
        self._set_user_hint(user_uuid, True)

    def on_mobile_refresh_token_deleted(self, user_uuid):
        try:
            response = self._auth_client.token.list(user_uuid, mobile=True)
        except requests.HTTPError as e:
            logger.error(
                'failed to check if user %s still has a mobile refresh token: %s: %s',
                user_uuid,
                type(e).__name__,
                e,
            )
            return

        mobile = response['filtered'] > 0
        self._set_user_hint(user_uuid, mobile)

    def send_push_notification(
        self,
        tenant_uuid,
        user_uuid,
        call_id,
        sip_call_id,
        caller_id_name,
        caller_id_number,
        video_enabled,
        ring_timeout,
        origin_call_id,
        push_mobile_timestamp,
    ):
        payload = {
            'peer_caller_id_number': caller_id_number,
            'peer_caller_id_name': caller_id_name,
            'call_id': call_id,
            'video': video_enabled,
            'ring_timeout': ring_timeout,
            'sip_call_id': sip_call_id,
            'mobile_wakeup_timestamp': push_mobile_timestamp,
        }

        self._pending_push_mobile[call_id] = PendingPushMobile(
            call_id,
            tenant_uuid,
            user_uuid,
            payload,
        )

        self._call_ring_time[origin_call_id] = ring_timeout

        self._notifier.push_notification(payload, tenant_uuid, user_uuid)

    def cancel_push_mobile(self, call_id):
        pending_push = self._pending_push_mobile.pop(call_id, None)
        if not pending_push:
            return

        self._notifier.cancel_push_notification(
            pending_push.payload,
            pending_push.tenant_uuid,
            pending_push.user_uuid,
        )

    def remove_pending_push_mobile(self, call_id):
        self._pending_push_mobile.pop(call_id, None)

    def has_a_registered_mobile_and_pending_push(
        self, push_call_id, call_id, endpoint, user_uuid
    ):
        pending_push = self._pending_push_mobile.get(push_call_id)
        if not pending_push:
            return False

        if user_uuid != pending_push.user_uuid:
            return False

        raw_contacts = self._ari.channels.getChannelVar(
            channelId=call_id,
            variable=f'PJSIP_AOR({endpoint},contact)',
        )['value']
        for contact in raw_contacts.split(','):
            if not contact:
                continue
            mobility = self._ari.channels.getChannelVar(
                channelId=call_id, variable=f'PJSIP_CONTACT({contact},mobility)'
            )['value']
            if mobility == 'mobile':
                return True
        return False
