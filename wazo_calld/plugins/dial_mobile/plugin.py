# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid
import time
import logging
import threading

from ari.exceptions import ARINotFound

logger = logging.getLogger(__name__)


class Plugin:

    def load(self, dependencies):
        ari = dependencies['ari']

        service = DialMobileService(ari)

        stasis = DialMobileStasis(ari, service)
        stasis.subscribe()
        stasis.add_ari_application()


class _ContactPoller:

    def __init__(self, ari, future_bridge_uuid, channel_id, aor):
        self._ari = ari
        self.future_bridge_uuid = future_bridge_uuid
        self.should_stop = threading.Event()
        self._thread = threading.Thread(
            name='ContactPoller',
            target=self._run,
            args=(channel_id, aor),
        )
        self._called_contacts = set()
        self.is_running = False

    def start(self):
        self._thread.start()

    def stop(self):
        if not self._thread.is_alive():
            return

        logger.critical('stopping poller')
        self.should_stop.set()
        self._thread.join()
        logger.critical('poller stopped')

    def _run(self, channel_id, aor):
        logger.info('poller started')
        start_time = time.time()
        channel = self._ari.channels.get(channelId=channel_id)
        caller_id = '"{name}" <{number}>'.format(**channel.json['caller'])

        while True:
            contacts = self._get_contacts(channel_id, aor)
            for contact in contacts:
                if self.should_stop.is_set():
                    logger.info('should stop is set')
                    break

                if contact in self._called_contacts:
                    continue

                self._called_contacts.add(contact)
                logger.info('new contact %s', contact)
                self._send_contact_to_current_call(contact, self.future_bridge_uuid, caller_id)

            # Avoid leaking threads if the calls have been answered elsewhere
            if time.time() - start_time > 30:
                self.should_stop.set()

            if self.should_stop.is_set():
                break

            time.sleep(0.25)

    def _send_contact_to_current_call(self, contact, future_bridge_uuid, caller_id):
        logger.info('Sending %s to the future bridge %s', contact, future_bridge_uuid)
        result = self._ari.channels.originate(
            endpoint=contact,
            app='dial_mobile',
            appArgs=['join', future_bridge_uuid],
            callerId=caller_id,
        )
        logger.info('%s', result)

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


class DialMobileService:

    def __init__(self, ari):
        self._ari = ari.client
        self._contact_pollers = {}
        self._outgoing_calls = {}

    def dial_all_contacts(self, channel_id, aor):
        logger.info('dial_all_contacts(%s, %s)', channel_id, aor)
        future_bridge_uuid = str(uuid.uuid4())

        logger.info('%s is waiting for a channel to join the bridge %s', future_bridge_uuid)
        poller = _ContactPoller(self._ari, future_bridge_uuid, channel_id, aor)
        self._contact_pollers[future_bridge_uuid] = poller
        self._outgoing_calls[future_bridge_uuid] = channel_id
        logger.info('starting poller')
        poller.start()

    def join_bridge(self, channel_id, future_bridge_uuid):
        logger.info('%s is joining bridge %s', channel_id, future_bridge_uuid)
        self._contact_pollers[future_bridge_uuid].stop()
        outgoing_channel_id = self._outgoing_calls[future_bridge_uuid]
        logger.critical('answering %s', channel_id)
        try:
            self._ari.channels.answer(channelId=channel_id)
        except ARINotFound as e:
            logger.critical('%s', e)
            logger.critical('%s', e.__dict__)
            logger.critical('%s', e.original_error.response.text)

        logger.critical('answering %s', outgoing_channel_id)
        try:
            self._ari.channels.answer(channelId=outgoing_channel_id)
        except ARINotFound as e:
            logger.critical('%s', e)
            logger.critical('%s', e.__dict__)
            logger.critical('%s', e.original_error.response.text)

        bridge = self._ari.bridges.createWithId(
            type='mixing',
            bridgeId=future_bridge_uuid,
        )
        bridge.addChannel(channel=channel_id)
        bridge.addChannel(channel=outgoing_channel_id)


class DialMobileStasis:

    _app_name = 'dial_mobile'

    def __init__(self, ari, service):
        self._core_ari = ari
        self._ari = ari.client
        self._service = service

    def stasis_start(self, event_object, event):
        if event['application'] != self._app_name:
            return

        logger.info('%s', event)
        action = event['args'][0]
        channel_id = event['channel']['id']
        logger.info('action: %s channel_id: %s', action, channel_id)

        if action == 'dial':
            aor = event['args'][1]
            self._service.dial_all_contacts(channel_id, aor)
        elif action == 'join':
            future_bridge_uuid = event['args'][1]
            self._service.join_bridge(channel_id, future_bridge_uuid)

    def stasis_end(self, event_object, event):
        logger.info('%s', event)

    def add_ari_application(self):
        self._core_ari.register_application(self._app_name)
        self._core_ari.reload()

    def subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('StasisEnd', self.stasis_end)
