# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.status import Status
from xivo_bus.consumer import BusConsumer
from xivo_bus.publisher import BusPublisher


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
