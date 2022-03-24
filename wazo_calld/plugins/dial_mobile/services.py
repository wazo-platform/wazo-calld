# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid
import time
import threading
import logging

from ari.exceptions import ARINotFound
from wazo_calld.plugin_helpers.ari_ import Bridge


logger = logging.getLogger(__name__)


class _NoSuchChannel(Exception):
    pass


class _PollingContactDialer:

    def __init__(self, ari, future_bridge_uuid, channel_id, aor):
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

    def start(self):
        self._thread.start()

    def stop(self):
        if not self._thread.is_alive():
            return

        self.should_stop.set()
        self._thread.join()

    def _run_no_exception(self, *args, **kwargs):
        try:
            return self._run(*args, **kwargs)
        except Exception:
            logger.exception('Unhandled exception in %s thread', self._thread.name)

    def _run(self, channel_id, aor):
        logger.debug('%s thread starting', self._thread.name)
        channel = self._ari.channels.get(channelId=channel_id)
        caller_id = '"{name}" <{number}>'.format(**channel.json['caller'])

        while True:
            contacts = self._get_contacts(channel_id, aor)
            for contact in contacts:
                if self.should_stop.is_set():
                    break

                self._send_contact_to_current_call(contact, self.future_bridge_uuid, caller_id)

            if not self._channel_is_up(channel_id):
                logger.debug('calling channel is gone: stopping %s thread', self._thread.name)
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

        logger.debug('sending %s to the future bridge %s', contact, future_bridge_uuid)
        channel = self._ari.channels.originate(
            endpoint=contact,
            app='dial_mobile',
            appArgs=['join', future_bridge_uuid],
            callerId=caller_id,
            originator=self._caller_channel_id,
        )

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
        asterisk_dialplan_function = 'PJSIP_DIAL_CONTACTS({})'.format(aor)
        try:
            response = self._ari.channels.getChannelVar(
                channelId=channel_id,
                variable=asterisk_dialplan_function,
            )
            return [contact for contact in response['value'].split('&') if contact]
        except ARINotFound:
            return []

    def _on_channel_gone(self, channel_id):
        for channel in self._dialed_channels:
            if channel.id != channel_id:
                continue

            self.stop()
            try:
                self._ari.channels.hangup(channelId=self._caller_channel_id)
            except ARINotFound:
                pass  # Already gone
            return

        raise _NoSuchChannel(channel_id)


class DialMobileService:

    def __init__(self, ari, amid_client):
        self._ari = ari.client
        self._amid_client = amid_client
        self._contact_dialers = {}
        self._outgoing_calls = {}

    def dial_all_contacts(self, caller_channel_id, aor):
        self._ari.channels.ring(channelId=caller_channel_id)

        logger.info('dial_all_contacts(%s, %s)', caller_channel_id, aor)
        future_bridge_uuid = str(uuid.uuid4())

        logger.debug('%s is waiting for a channel to join the bridge %s', caller_channel_id, future_bridge_uuid)
        dialer = _PollingContactDialer(self._ari, future_bridge_uuid, caller_channel_id, aor)
        self._contact_dialers[future_bridge_uuid] = dialer
        self._outgoing_calls[future_bridge_uuid] = caller_channel_id
        dialer.start()

    def join_bridge(self, channel_id, future_bridge_uuid):
        logger.info('%s is joining bridge %s', channel_id, future_bridge_uuid)
        dialer = self._contact_dialers.pop(future_bridge_uuid, None)
        if not dialer:
            return

        dialer.stop()
        outgoing_channel_id = self._outgoing_calls[future_bridge_uuid]
        try:
            self._ari.channels.answer(channelId=outgoing_channel_id)
        except ARINotFound:
            logger.info('the caller (%s) left the call before being bridged')
            return

        try:
            self._ari.channels.answer(channelId=channel_id)
        except ARINotFound:
            logger.info('the answered (%s) left the call before being bridged')
            return

        bridge = self._ari.bridges.createWithId(
            type='mixing',
            bridgeId=future_bridge_uuid,
        )
        # Without the inhibitConnectedLineUpdates everyone in the bridge will receive a new
        # connected line update with the caller ID of the caller when PAI is trusted, including
        # the caller...
        bridge.addChannel(channel=channel_id, inhibitConnectedLineUpdates=True)
        bridge.addChannel(channel=outgoing_channel_id, inhibitConnectedLineUpdates=True)

    def notify_channel_gone(self, channel_id):
        to_remove = None

        for key, dialer in self._contact_dialers.items():
            try:
                dialer._on_channel_gone(channel_id)
            except _NoSuchChannel:
                continue
            else:
                to_remove = key

        if to_remove:
            del self._contact_dialers[key]

    def clean_bridge(self, bridge_id):
        bridge_helper = Bridge(bridge_id, self._ari)
        if bridge_helper.has_lone_channel():
            logger.debug('dial_mobile: bridge %s: only one participant left, hanging up', bridge_id)
            bridge_helper.hangup_all()
        elif bridge_helper.is_empty():
            logger.debug('dial_mobile bridge %s: bridge is empty, destroying', bridge_id)
            try:
                self._ari.bridges.destroy(bridgeId=bridge_id)
            except ARINotFound:
                pass

    def on_calld_stopping(self):
        for dialer in self._contact_dialers.values():
            dialer.stop()

    def set_user_hint(self, user_uuid, has_mobile_sessions):
        self._amid_client.action(
            'Setvar',
            {
                'Variable': f'DEVICE_STATE(Custom:{user_uuid}-mobile)',
                'Value': 'NOT_INUSE' if has_mobile_sessions else 'UNAVAILABLE',
            },
        )
