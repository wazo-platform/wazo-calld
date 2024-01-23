# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_bus.consumer import BusConsumer
from wazo_bus.publisher import BusPublisher
from xivo.status import Status


class CoreBusConsumer(BusConsumer):
    @classmethod
    def from_config(cls, bus_config):
        name = 'wazo-calld'
        return cls(name=name, **bus_config)

    def provide_status(self, status):
        status['bus_consumer']['status'] = (
            Status.ok if self.consumer_connected() else Status.fail
        )


class CoreBusPublisher(BusPublisher):
    @classmethod
    def from_config(cls, service_uuid, bus_config):
        name = 'wazo-calld'
        return cls(name=name, service_uuid=service_uuid, **bus_config)
