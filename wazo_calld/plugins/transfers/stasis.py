# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging

from xivo.pubsub import Pubsub

from ari.exceptions import ARINotFound
from ari.exceptions import ARINotInStasis

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME
from wazo_calld.exceptions import WazoAmidError
from wazo_calld.helpers.ari_ import Channel

from . import ari_helpers
from .event import (
    CreateTransferEvent,
    TransferRecipientAnsweredEvent
)
from .exceptions import (
    InvalidEvent,
    TransferException,
)
from .lock import HangupLock, InvalidLock
from .transfer import TransferRole

logger = logging.getLogger(__name__)


class TransfersStasis:

    def __init__(self, amid_client, ari_client, services, state_factory, state_persistor, xivo_uuid):
        self.ari = ari_client
        self.amid = amid_client
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.stasis_start_pubsub = Pubsub()
        self.stasis_start_pubsub.set_exception_handler(self.invalid_event)
        self.hangup_pubsub = Pubsub()
        self.hangup_pubsub.set_exception_handler(self.invalid_event)
        self.state_factory = state_factory
        self.state_persistor = state_persistor

    def subscribe(self):
        self.ari.on_application_registered(DEFAULT_APPLICATION_NAME, self.process_lost_hangups)
        self.ari.on_channel_event('ChannelEnteredBridge', self.release_hangup_lock)
        self.ari.on_channel_event('ChannelDestroyed', self.bypass_hangup_lock_from_source)
        self.ari.on_bridge_event('BridgeDestroyed', self.clean_bridge_variables)

        self.ari.on_channel_event('ChannelLeftBridge', self.clean_bridge)

        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.stasis_start_pubsub.subscribe('transfer_recipient_called', self.transfer_recipient_answered)
        self.stasis_start_pubsub.subscribe('create_transfer', self.create_transfer)

        self.ari.on_channel_event('ChannelDestroyed', self.hangup)
        self.ari.on_channel_event('StasisEnd', self.hangup)
        self.ari.on_channel_event('ChannelMohStop', self.moh_stop)
        self.hangup_pubsub.subscribe(TransferRole.recipient, self.recipient_hangup)
        self.hangup_pubsub.subscribe(TransferRole.initiator, self.initiator_hangup)
        self.hangup_pubsub.subscribe(TransferRole.transferred, self.transferred_hangup)

        self.ari.on_channel_event('ChannelCallerId', self.update_transfer_caller_id)

    def moh_stop(self, channel, event):
        logger.debug('received ChannelMohStop for channel %s (%s)', channel.id, event['channel']['name'])
        try:
            transfer = self.state_persistor.get_by_channel(channel.id)
        except KeyError:
            logger.debug('ignoring ChannelMohStop event: channel %s, app %s', event['channel']['name'], event['application'])
            return

        transfer_role = transfer.role(channel.id)
        if transfer_role != TransferRole.transferred:
            logger.debug('ignoring ChannelMohStop event: channel %s, app %s', event['channel']['name'], event['application'])
            return

        transfer_state = self.state_factory.make(transfer)
        transfer_state.transferred_moh_stop()

    def invalid_event(self, _, __, exception):
        if isinstance(exception, InvalidEvent):
            event = exception.event
            logger.error('invalid stasis event received: %s', event)
        elif (isinstance(exception, WazoAmidError)
              or isinstance(exception, TransferException)):
            self.handle_error(exception)
        else:
            raise exception

    def handle_error(self, exception):
        logger.error('%s: %s', exception.message, exception.details)

    def process_lost_hangups(self):
        transfers = list(self.state_persistor.list())

        logger.debug('Processing lost hangups since last stop...')
        for transfer in transfers:
            transfer_state = self.state_factory.make(transfer)
            if not Channel(transfer.transferred_call, self.ari).exists():
                logger.debug('Transferred hangup from transfer %s', transfer.id)
                transfer_state = transfer_state.transferred_hangup()
            if not Channel(transfer.initiator_call, self.ari).exists():
                logger.debug('Initiator hangup from transfer %s', transfer.id)
                transfer_state = transfer_state.initiator_hangup()
            if not Channel(transfer.recipient_call, self.ari).exists():
                logger.debug('Recipient hangup from transfer %s', transfer.id)
                transfer_state = transfer_state.recipient_hangup()
        logger.debug('Done.')

    def stasis_start(self, event_objects, event):
        channel = event_objects['channel']
        try:
            app_action = event['args'][1]
        except IndexError:
            logger.debug('ignoring StasisStart event: channel %s, app %s, args %s',
                         event['channel']['name'],
                         event['application'],
                         event['args'])
            return
        self.stasis_start_pubsub.publish(app_action, (channel, event))

    def hangup(self, channel, event):
        try:
            transfer = self.state_persistor.get_by_channel(channel.id)
        except KeyError:
            logger.debug('ignoring StasisEnd event: channel %s, app %s', event['channel']['name'], event['application'])
            return
        transfer_role = transfer.role(channel.id)
        self.hangup_pubsub.publish(transfer_role, transfer)

    def transfer_recipient_answered(self, channel_event):
        channel, event = channel_event
        event = TransferRecipientAnsweredEvent(event)

        try:
            transfer_bridge = self.ari.bridges.get(bridgeId=event.transfer_bridge)
            transfer_bridge.addChannel(channel=channel.id)
        except ARINotFound:
            logger.error('recipient answered, but transfer was hung up')
            return

        try:
            transfer = self.state_persistor.get(event.transfer_bridge)
        except KeyError:
            logger.debug('recipient answered, but transfer was abandoned')

            for channel_id in transfer_bridge.json['channels']:
                try:
                    ari_helpers.unring_initiator_call(self.ari, channel_id)
                except ARINotFound:
                    pass
        else:
            logger.debug('recipient answered, transfer continues normally')
            transfer_state = self.state_factory.make(transfer)
            transfer_state.recipient_answer()

    def create_transfer(self, channel_event):
        channel, event = channel_event
        event = CreateTransferEvent(event)
        try:
            bridge = self.ari.bridges.get(bridgeId=event.transfer_id)
        except ARINotFound:
            bridge = self.ari.bridges.createWithId(type='mixing', name='transfer', bridgeId=event.transfer_id)

        bridge.addChannel(channel=channel.id)
        channel_ids = bridge.get().json['channels']
        if len(channel_ids) == 2:
            transfer = self.state_persistor.get(event.transfer_id)
            try:
                context = self.ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_RECIPIENT_CONTEXT')['value']
                exten = self.ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_RECIPIENT_EXTEN')['value']
                variables_str = self.ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_VARIABLES')['value']
                timeout_str = self.ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_TIMEOUT')['value']
            except ARINotFound:
                logger.error('initiator hung up while creating transfer')
            try:
                variables = json.loads(variables_str)
            except ValueError:
                logger.warning('could not decode transfer variables "%s"', variables_str)
                variables = {}
            timeout = None if timeout_str == 'None' else int(timeout_str)

            transfer_state = self.state_factory.make(transfer)
            new_state = transfer_state.start(transfer, context, exten, variables, timeout)
            if new_state.transfer.flow == 'blind':
                new_state.complete()

    def recipient_hangup(self, transfer):
        logger.debug('recipient hangup = cancel transfer %s', transfer.id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.recipient_hangup()

    def initiator_hangup(self, transfer):
        logger.debug('initiator hangup = complete transfer %s', transfer.id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.initiator_hangup()

    def transferred_hangup(self, transfer):
        logger.debug('transferred hangup = abandon transfer %s', transfer.id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.transferred_hangup()

    def clean_bridge(self, channel, event):
        try:
            bridge = self.ari.bridges.get(bridgeId=event['bridge']['id'])
        except ARINotFound:
            return
        if bridge.json['bridge_type'] != 'mixing':
            return

        logger.debug('cleaning bridge %s', bridge.id)
        try:
            self.ari.channels.get(channelId=channel.id)
            channel_is_hungup = False
        except ARINotFound:
            logger.debug('channel who left was hungup')
            channel_is_hungup = True

        if len(bridge.json['channels']) == 1 and channel_is_hungup:
            logger.debug('one channel left in bridge %s', bridge.id)
            lone_channel_id = bridge.json['channels'][0]

            try:
                bridge_is_locked = HangupLock.from_target(self.ari, bridge.id)
            except InvalidLock:
                bridge_is_locked = False

            if not bridge_is_locked:
                logger.debug('emptying bridge %s', bridge.id)
                try:
                    self.ari.channels.hangup(channelId=lone_channel_id)
                except ARINotFound:
                    pass

        try:
            bridge = bridge.get()
        except ARINotFound:
            return
        if len(bridge.json['channels']) == 0:
            self.bypass_hangup_lock_from_target(bridge)

            logger.debug('destroying bridge %s', bridge.id)
            try:
                bridge.destroy()
            except (ARINotInStasis, ARINotFound):
                pass

    def clean_bridge_variables(self, bridge, event):
        global_variable = 'XIVO_BRIDGE_VARIABLES_{}'.format(bridge.id)
        self.ari.asterisk.setGlobalVar(variable=global_variable, value='')

    def release_hangup_lock(self, channel, event):
        lock_source = channel
        lock_target_candidate_id = event['bridge']['id']
        try:
            lock = HangupLock(self.ari, lock_source.id, lock_target_candidate_id)
            lock.release()
        except InvalidLock:
            pass

    def bypass_hangup_lock_from_source(self, channel, event):
        lock_source = channel
        for lock in HangupLock.from_source(self.ari, lock_source.id):
            lock.kill_target()

    def bypass_hangup_lock_from_target(self, bridge):
        try:
            lock = HangupLock.from_target(self.ari, bridge.id)
            lock.kill_source()
        except InvalidLock:
            pass

    def update_transfer_caller_id(self, channel, event):
        try:
            transfer = self.state_persistor.get_by_channel(channel.id)
        except KeyError:
            logger.debug('ignoring ChannelCallerId event: channel %s', event['channel']['name'])
            return

        transfer_role = transfer.role(channel.id)
        if transfer_role != TransferRole.recipient:
            logger.debug('ignoring ChannelCallerId event: channel %s', event['channel']['name'])
            return

        try:
            ari_helpers.update_connectedline(self.ari,
                                             self.amid,
                                             transfer.initiator_call,
                                             transfer.recipient_call)
        except ARINotFound:
            try:
                ari_helpers.update_connectedline(self.ari,
                                                 self.amid,
                                                 transfer.transferred_call,
                                                 transfer.recipient_call)
            except ARINotFound:
                logger.debug('cannot update transfer callerid: everyone hung up')
