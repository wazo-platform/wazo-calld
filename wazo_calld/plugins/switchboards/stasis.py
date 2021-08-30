# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

from .exceptions import NoSuchSwitchboard

logger = logging.getLogger(__name__)


class SwitchboardsStasis:
    def __init__(self, ari, confd, switchboard_notifier, switchboard_service):
        self._ari = ari.client
        self._core_ari = ari
        self._confd = confd
        self._notifier = switchboard_notifier
        self._service = switchboard_service

    def initialize(self):
        self._subscribe()
        self._core_ari.register_application(DEFAULT_APPLICATION_NAME)

    def _subscribe(self):
        self._ari.on_application_registered(
            DEFAULT_APPLICATION_NAME, self.notify_all_switchboard_queued
        )
        self._ari.on_application_registered(
            DEFAULT_APPLICATION_NAME, self.notify_all_switchboard_held
        )
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('ChannelLeftBridge', self.unqueue)
        self._ari.on_channel_event('ChannelLeftBridge', self.unhold)

    def notify_all_switchboard_queued(self):
        for switchboard in self._confd.switchboards.list(recurse=True)['items']:
            queued_calls = self._service.queued_calls(
                switchboard['tenant_uuid'], switchboard['uuid']
            )
            self._notifier.queued_calls(
                switchboard['tenant_uuid'], switchboard['uuid'], queued_calls
            )

    def notify_all_switchboard_held(self):
        for switchboard in self._confd.switchboards.list(recurse=True)['items']:
            held_calls = self._service.held_calls(
                switchboard['tenant_uuid'], switchboard['uuid']
            )
            self._notifier.held_calls(
                switchboard['tenant_uuid'], switchboard['uuid'], held_calls
            )

    def stasis_start(self, event_objects, event):
        if len(event['args']) < 2:
            return

        try:
            # app_instance = event['args'][0]
            if event['args'][1] == 'switchboard_queue':
                self._stasis_start_queue(event_objects, event)
            elif event['args'][1] == 'switchboard_answer':
                self._stasis_start_answer(event_objects, event)
            elif event['args'][1] == 'switchboard_unhold':
                self._stasis_start_answer_held(event_objects, event)
        except Exception:
            logger.exception('failed handle a stasis_start %s', event)
            self._ari.channels.continueInDialplan(channelId=event_objects['channel'].id)

    def _stasis_start_queue(self, event_objects, event):
        try:
            tenant_uuid = event['args'][2]
            switchboard_uuid = event['args'][3]
        except IndexError:
            logger.warning('Ignoring invalid StasisStart event %s', event)
            return
        channel = event_objects['channel']
        self._service.new_queued_call(tenant_uuid, switchboard_uuid, channel.id)

    def _stasis_start_answer(self, event_objects, event):
        try:
            tenant_uuid = event['args'][2]
            switchboard_uuid = event['args'][3]
            queued_channel_id = event['args'][4]
        except IndexError:
            logger.warning('Ignoring invalid StasisStart event %s', event)
            return
        operator_channel = event_objects['channel']

        try:
            self._ari.channels.get(channelId=queued_channel_id)
        except ARINotFound:
            logger.warning(
                'queued call %s hung up, cancelling answer from switchboard %s',
                queued_channel_id,
                switchboard_uuid,
            )
            operator_channel.hangup()
            return

        operator_channel.answer()
        try:
            operator_original_caller_id = operator_channel.getChannelVar(
                variable='XIVO_ORIGINAL_CALLER_ID'
            )['value'].encode('utf-8')
            operator_channel.setChannelVar(
                variable='CALLERID(all)', value=operator_original_caller_id
            )
        except ARINotFound:
            pass

        bridge = self._ari.bridges.create(type='mixing')
        bridge.addChannel(channel=queued_channel_id)
        bridge.addChannel(channel=operator_channel.id)

        self._notifier.queued_call_answered(
            tenant_uuid, switchboard_uuid, operator_channel.id, queued_channel_id
        )

    def _stasis_start_answer_held(self, event_objects, event):
        try:
            tenant_uuid = event['args'][2]
            switchboard_uuid = event['args'][3]
            held_channel_id = event['args'][4]
        except IndexError:
            logger.warning('Ignoring invalid StasisStart event %s', event)
            return
        operator_channel = event_objects['channel']

        try:
            self._ari.channels.get(channelId=held_channel_id)
        except ARINotFound:
            logger.warning(
                'held call %s hung up, cancelling answer from switchboard %s',
                held_channel_id,
                switchboard_uuid,
            )
            operator_channel.hangup()
            return

        operator_channel.answer()
        try:
            operator_original_caller_id = operator_channel.getChannelVar(
                variable='XIVO_ORIGINAL_CALLER_ID'
            )['value'].encode('utf-8')
            operator_channel.setChannelVar(
                variable='CALLERID(all)', value=operator_original_caller_id
            )
        except ARINotFound:
            pass

        bridge = self._ari.bridges.create(type='mixing')
        bridge.addChannel(channel=held_channel_id)
        bridge.addChannel(channel=operator_channel.id)

        self._notifier.held_call_answered(
            tenant_uuid, switchboard_uuid, operator_channel.id, held_channel_id
        )

    def unqueue(self, channel, event):
        switchboard_uuid = channel.json['channelvars']['WAZO_SWITCHBOARD_QUEUE']
        tenant_uuid = channel.json['channelvars']['WAZO_TENANT_UUID']

        try:
            queued_calls = self._service.queued_calls(tenant_uuid, switchboard_uuid)
        except NoSuchSwitchboard:
            return

        self._notifier.queued_calls(tenant_uuid, switchboard_uuid, queued_calls)

    def unhold(self, channel, event):
        switchboard_uuid = channel.json['channelvars']['WAZO_SWITCHBOARD_HOLD']
        tenant_uuid = channel.json['channelvars']['WAZO_TENANT_UUID']

        try:
            held_calls = self._service.held_calls(tenant_uuid, switchboard_uuid)
        except NoSuchSwitchboard:
            return

        self._notifier.held_calls(tenant_uuid, switchboard_uuid, held_calls)
