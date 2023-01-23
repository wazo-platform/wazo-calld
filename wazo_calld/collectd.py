# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.base import Base
from xivo_bus.mixins import QueuePublisherMixin, ThreadableMixin, CollectdMixin


class CollectdPublisher(CollectdMixin, QueuePublisherMixin, ThreadableMixin, Base):
    @classmethod
    def from_config(cls, service_uuid, bus_config, collectd_config):
        config = dict(bus_config)
        config.update(**collectd_config)
        return cls(name='collectd', service_uuid=service_uuid, **config)
