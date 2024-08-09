# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any, TypedDict

from flask_restful import Api
from xivo.pubsub import Pubsub
from xivo.status import StatusAggregator

from .ari_ import CoreARI
from .asyncio_ import CoreAsyncio
from .bus import CoreBusConsumer, CoreBusPublisher
from .collectd import CollectdPublisher

TokenRenewalCallback = Callable[[Collection[str]], None]


class PluginDependencies(TypedDict):
    api: Api
    ari: CoreARI
    asyncio: CoreAsyncio
    bus_publisher: CoreBusPublisher
    bus_consumer: CoreBusConsumer
    collectd: CollectdPublisher
    config: dict
    status_aggregator: StatusAggregator
    pubsub: Pubsub
    token_changed_subscribe: Callable[[TokenRenewalCallback], None]
    next_token_changed_subscribe: Callable[[TokenRenewalCallback], None]


class StatusDict(TypedDict):
    plugins: dict[str, Any]
