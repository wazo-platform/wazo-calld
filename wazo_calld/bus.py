# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.status import Status
from xivo_bus.consumer import BusConsumer
from xivo_bus.publisher import BusPublisher


class CoreBusConsumer(BusConsumer):
    def provide_status(self, status):
        status['bus_consumer']['status'] = (
            Status.ok if self.is_running else Status.fail
        )


class CoreBusPublisher(BusPublisher):
    pass
