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


class AmidConfigDict(TypedDict):
    host: str
    port: int
    prefix: str | None
    https: bool


class AriConnectionConfigDict(TypedDict):
    base_url: str
    username: str
    password: str


class AriConfigDict(TypedDict):
    connection: AriConnectionConfigDict
    reconnection_delay: int
    startup_connection_delay: int


class AuthConfigDict(TypedDict):
    host: str
    port: int
    prefix: str | None
    https: bool
    key_file: str


class BusConfigDict(TypedDict):
    username: str
    password: str
    host: str
    port: int
    exchange_name: str
    exchange_type: str


class CollectdConfigDict(TypedDict):
    exchange_name: str
    exchange_type: str
    exchange_durable: bool


class ConfdConfigDict(TypedDict):
    host: str
    port: int
    prefix: str | None
    https: bool


class ConsulConfigDict(TypedDict):
    scheme: str
    port: int


class PhonedConfigDict(TypedDict):
    host: str
    port: int
    prefix: str | None
    https: bool


class RestApiCorsConfigDict(TypedDict):
    enabled: bool
    allow_headers: list[str]


class RestApiConfigDict(TypedDict):
    listen: str
    port: int
    certificate: str | None
    private_key: str | None
    cors: RestApiCorsConfigDict
    max_threads: int


class ServiceDiscoveryConfigDict(TypedDict):
    enabled: bool
    advertise_address: str
    advertise_address_interface: str
    advertise_port: int
    ttl_interval: int
    refresh_interval: int
    retry_interval: int


class CalldConfigDict(TypedDict):
    config_file: str
    extra_config_files: str
    debug: bool
    log_level: str
    log_filename: str
    user: str
    amid: AmidConfigDict
    ari: AriConfigDict
    auth: AuthConfigDict
    bus: BusConfigDict
    collectd: CollectdConfigDict
    confd: ConfdConfigDict
    consul: ConsulConfigDict
    enabled_plugins: dict[str, bool]
    max_meeting_participants: int
    phoned: PhonedConfigDict
    remote_credentials: dict[str, Any]
    rest_api: RestApiConfigDict
    service_discovery: ServiceDiscoveryConfigDict


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
