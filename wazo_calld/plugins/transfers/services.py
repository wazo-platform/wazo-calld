# Copyright 2016-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from wazo_amid_client import Client as AmidClient
from wazo_confd_client import Client as ConfdClient
from xivo.caller_id import assemble_caller_id

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME, ARIClientProxy
from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.ari_ import Channel
from wazo_calld.plugin_helpers.confd import User
from wazo_calld.plugin_helpers.exceptions import (
    InvalidExtension,
    NotEnoughChannels,
    TooManyChannels,
    UserPermissionDenied,
)

from .exceptions import (
    NoSuchTransfer,
    TooManyTransferredCandidates,
    TransferAlreadyStarted,
    TransferCreationError,
)
from .notifier import TransferNotifier
from .state import (
    StateFactory,
    TransferState,
    TransferStateNonStasis,
    TransferStateReady,
)
from .state_persistor import StatePersistor
from .transfer import Transfer
from .transfer_lock import TransferLock

logger = logging.getLogger(__name__)


class TransfersService:
    def __init__(
        self,
        amid_client,
        ari,
        confd_client,
        notifier,
        state_factory,
        state_persistor,
        transfer_lock,
    ):
        self.amid_client: AmidClient = amid_client
        self.ari: ARIClientProxy = ari
        self.confd_client: ConfdClient = confd_client
        self.notifier: TransferNotifier = notifier
        self.state_persistor: StatePersistor = state_persistor
        self.state_factory: StateFactory = state_factory
        self.transfer_lock: TransferLock = transfer_lock

    def list_from_user(self, user_uuid):
        transfers = self.state_persistor.list()
        return [
            transfer for transfer in transfers if transfer.initiator_uuid == user_uuid
        ]

    def create(
        self, transferred_call, initiator_call, context, exten, flow, variables, timeout
    ):
        logger.debug(
            'Creating transfer: initiator_call=%s, transferred_call=%s,'
            'context=%s, exten=%s, flow=%s, timeout=%s',
            initiator_call,
            transferred_call,
            context,
            exten,
            flow,
            timeout,
        )
        try:
            transferred_channel = self.ari.channels.get(channelId=transferred_call)
            initiator_channel = self.ari.channels.get(channelId=initiator_call)
        except ARINotFound:
            raise TransferCreationError('channel not found')

        if not ami.extension_exists(self.amid_client, context, exten):
            raise InvalidExtension(context, exten)

        if not self.transfer_lock.acquire(initiator_call):
            raise TransferAlreadyStarted(initiator_call)

        channel = Channel(initiator_channel.id, self.ari)
        initiator_uuid = channel.user()
        if initiator_uuid is None:
            raise TransferCreationError('initiator has no user UUID')
        initiator_tenant_uuid = channel.tenant_uuid()
        transfer = Transfer(
            initiator_uuid=initiator_uuid,
            initiator_tenant_uuid=initiator_tenant_uuid,
            transferred_call=transferred_channel.id,
            initiator_call=initiator_channel.id,
            flow=flow,
        )

        transfer_state: TransferState
        transfer_state_class: type[TransferState]
        if not (
            Channel(transferred_call, self.ari).is_in_stasis()
            and Channel(initiator_call, self.ari).is_in_stasis()
        ):
            transfer_state_class = TransferStateNonStasis
        else:
            transfer_state_class = TransferStateReady

        with self.state_factory.make_from_class(
            transfer_state_class, transfer
        ) as transfer_state:
            try:
                new_state = transfer_state.start(context, exten, variables, timeout)
            except Exception:
                self.transfer_lock.release(initiator_call)
                raise

            self.notifier.created(new_state.transfer)

            if flow == 'blind':
                new_state = new_state.complete()

        return new_state.transfer

    def create_from_user(self, initiator_call, exten, flow, timeout, user_uuid):
        if not Channel(initiator_call, self.ari).exists():
            raise TransferCreationError('initiator channel not found')

        if Channel(initiator_call, self.ari).user() != user_uuid:
            raise UserPermissionDenied(user_uuid, {'call': initiator_call})

        try:
            transferred_call = (
                Channel(initiator_call, self.ari).only_connected_channel().id
            )
        except TooManyChannels as e:
            raise TooManyTransferredCandidates(e.channels)
        except NotEnoughChannels:
            raise TransferCreationError('transferred channel not found')

        context = User(user_uuid, self.confd_client).main_line().context()

        return self.create(
            transferred_call,
            initiator_call,
            context,
            exten,
            flow,
            variables={},
            timeout=timeout,
        )

    def originate_recipient(
        self, initiator_call, context, exten, transfer_id, variables, timeout
    ):
        initiator_channel = self.ari.channels.get(channelId=initiator_call)
        caller_id = assemble_caller_id(
            initiator_channel.json['caller']['name'],
            initiator_channel.json['caller']['number'],
        ).encode('utf-8')
        recipient_endpoint = 'Local/{exten}@{context}'.format(
            exten=exten, context=context
        )
        app_args = ['transfer', 'transfer_recipient_called', transfer_id]
        originate_variables = dict(variables)
        originate_variables['XIVO_TRANSFER_ROLE'] = 'recipient'
        originate_variables['XIVO_TRANSFER_ID'] = transfer_id
        originate_variables['CHANNEL(language)'] = initiator_channel.getChannelVar(
            variable='CHANNEL(language)'
        )['value']
        try:
            user_id = initiator_channel.getChannelVar(variable='WAZO_USERID')['value']
            originate_variables['XIVO_USERID'] = user_id  # Deprecated in 24.01
            originate_variables['WAZO_USERID'] = user_id
        except ARINotFound:
            pass
        try:
            user_uuid = initiator_channel.getChannelVar(variable='WAZO_USERUUID')[
                'value'
            ]
            originate_variables['WAZO_USERUUID'] = user_uuid
            originate_variables['XIVO_USERUUID'] = user_uuid  # Deprecated in 24.01
        except ARINotFound:
            pass
        timeout = -1 if timeout is None else timeout

        new_channel = self.ari.channels.originate(
            endpoint=recipient_endpoint,
            app=DEFAULT_APPLICATION_NAME,
            appArgs=app_args,
            callerId=caller_id,
            variables={'variables': originate_variables},
            timeout=timeout,
            originator=initiator_call,
        )
        recipient_call = new_channel.id

        return recipient_call

    def get(self, transfer_id):
        try:
            return self.state_persistor.get(transfer_id)
        except KeyError:
            raise NoSuchTransfer(transfer_id)

    def complete(self, transfer_id):
        try:
            with self.state_factory.make(transfer_id) as transfer_state:
                transfer_state.complete()
        except KeyError:
            raise NoSuchTransfer(transfer_id)

    def complete_from_user(self, transfer_id, user_uuid):
        transfer = self.get(transfer_id)
        if transfer.initiator_uuid != user_uuid:
            raise UserPermissionDenied(user_uuid, {'transfer': transfer_id})

        with self.state_factory.make(transfer_id) as transfer_state:
            transfer_state.complete()

    def cancel(self, transfer_id):
        try:
            with self.state_factory.make(transfer_id) as transfer_state:
                transfer_state.cancel()
        except KeyError:
            raise NoSuchTransfer(transfer_id)

    def cancel_from_user(self, transfer_id, user_uuid):
        transfer = self.get(transfer_id)
        if transfer.initiator_uuid != user_uuid:
            raise UserPermissionDenied(user_uuid, {'transfer': transfer_id})

        try:
            with self.state_factory.make(transfer_id) as transfer_state:
                transfer_state.cancel()
        except KeyError:
            raise NoSuchTransfer(transfer_id)
