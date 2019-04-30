# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.faxes.event import (
    FaxOutboundCreated,
    FaxOutboundFailed,
    FaxOutboundSucceeded,
    FaxOutboundUserCreated,
    FaxOutboundUserFailed,
    FaxOutboundUserSucceeded,
)


class FaxesNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def notify_fax_created(self, fax_infos):
        event = FaxOutboundCreated(fax_infos)
        self._bus_producer.publish(event)
        if fax_infos['user_uuid']:
            event = FaxOutboundUserCreated(fax_infos)
            self._bus_producer.publish(event)

    def notify_fax_succeeded(self, fax_infos):
        event = FaxOutboundSucceeded(fax_infos)
        self._bus_producer.publish(event)
        if fax_infos['user_uuid']:
            event = FaxOutboundUserSucceeded(fax_infos)
            self._bus_producer.publish(event)

    def notify_fax_failed(self, fax_infos):
        event = FaxOutboundFailed(fax_infos)
        self._bus_producer.publish(event)
        if fax_infos['user_uuid']:
            event = FaxOutboundUserFailed(fax_infos)
            self._bus_producer.publish(event)
