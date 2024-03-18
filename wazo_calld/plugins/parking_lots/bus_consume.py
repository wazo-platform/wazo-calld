# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging

from ari.exceptions import ARINotFound
from functools import wraps
from typing import Callable, TYPE_CHECKING

from wazo_calld.plugin_helpers.ari_ import set_channel_id_var_sync, Channel
from .dataclasses_ import AsteriskParkedCall
from .exceptions import NoSuchParking
from .helpers import split_parking_id_from_name, DONT_CHECK_TENANT

if TYPE_CHECKING:
    from wazo_calld.bus import CoreBusConsumer
    from wazo_calld.ari_ import CoreARI
    from .notifier import ParkingNotifier
    from .services import ParkingService


logger = logging.getLogger(__name__)
PARKED_CHANNEL_VAR = 'WAZO_CALL_PARKED'


def convert_ami_event(
    fn: Callable[[ParkingLotEventsHandler, AsteriskParkedCall, Channel], None],
) -> Callable[[ParkingLotEventsHandler, dict], None]:
    '''Helper decorator to convert AMI event dict to call and channel objects'''

    @wraps(fn)
    def wrapper(handler: ParkingLotEventsHandler, event: dict) -> None:
        if not isinstance(event, dict):
            raise ValueError('received invalid data')
        call = AsteriskParkedCall.from_dict(event)
        channel = handler._get_channel(call)
        return fn(handler, call, channel)

    return wrapper


class ParkingLotEventsHandler:
    def __init__(
        self,
        ari: CoreARI,
        consumer: CoreBusConsumer,
        notifier: ParkingNotifier,
        service: ParkingService,
    ):
        self._ari = ari
        self._notifier = notifier
        self._service = service
        consumer.subscribe('ParkedCall', self.on_ami_call_parked)
        consumer.subscribe('ParkedCallGiveUp', self.on_ami_parked_call_hangup)
        consumer.subscribe('ParkedCallSwap', self.on_ami_parked_call_swap)
        consumer.subscribe('ParkedCallTimeOut', self.on_ami_parked_call_timed_out)

    def _get_channel(self, call: AsteriskParkedCall) -> Channel:
        return Channel(call.parkee_uniqueid, self._ari.client)

    def _set_parked_status(self, channel: Channel, parked: bool) -> None:
        status = '1' if parked else ''
        try:
            set_channel_id_var_sync(
                self._ari.client,
                channel.id,
                PARKED_CHANNEL_VAR,
                status,
                bypass_stasis=True,
            )
        except ARINotFound:
            logger.error('channel not found: %s', channel.id)
            return
        else:
            logger.debug(
                'call has been marked as %s: %s',
                'parked' if parked else 'unparked',
                channel.id,
            )

    @convert_ami_event
    def on_ami_call_parked(
        self, parked_call: AsteriskParkedCall, parked_channel: Channel
    ) -> None:
        '''A call has been parked'''

        self._set_parked_status(parked_channel, True)

        if tenant_uuid := parked_channel.tenant_uuid():
            self._notifier.call_parked(parked_call, tenant_uuid)

    @convert_ami_event
    def on_ami_call_unparked(
        self, parked_call: AsteriskParkedCall, parked_channel: Channel
    ) -> None:
        '''A call has been unparked'''

        self._set_parked_status(parked_channel, False)
        retriever_channel = parked_channel.only_connected_channel()

        if tenant_uuid := parked_channel.tenant_uuid():
            self._notifier.call_unparked(parked_call, retriever_channel.id, tenant_uuid)

    @convert_ami_event
    def on_ami_parked_call_hangup(
        self, parked_call: AsteriskParkedCall, _: Channel
    ) -> None:
        '''A parked call has been hungup before being answered'''

        # Since channel is closed at this point, we must find the tenant_uuid some other way
        tenant_uuid = None
        try:
            id_ = split_parking_id_from_name(parked_call.parkinglot)
            parking = self._service.get_parking(DONT_CHECK_TENANT, id_)
        except (ValueError, NoSuchParking):
            logger.debug(
                'parked call hangup handler failed: couldn\'t determine tenant_uuid'
            )
        else:
            tenant_uuid = parking.tenant_uuid

        if tenant_uuid:
            self._notifier.parked_call_hangup(parked_call, tenant_uuid)

    @convert_ami_event
    def on_ami_parked_call_swap(
        self, _: AsteriskParkedCall, parked_channel: Channel
    ) -> None:
        '''A parked call has been swaped'''

        self._set_parked_status(parked_channel, False)

    @convert_ami_event
    def on_ami_parked_call_timed_out(
        self, parked_call: AsteriskParkedCall, parked_channel: Channel
    ) -> None:
        '''A parked call has timed out'''

        self._set_parked_status(parked_channel, False)

        if tenant_uuid := parked_channel.tenant_uuid():
            self._notifier.parked_call_timed_out(parked_call, tenant_uuid)
