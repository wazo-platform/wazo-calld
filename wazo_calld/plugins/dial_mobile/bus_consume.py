# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


class EventHandler:
    def __init__(self, service):
        self._service = service

    def subscribe(self, bus_consumer):
        bus_consumer.on_event('auth_refresh_token_created', self._on_refresh_token_created)
        bus_consumer.on_event('auth_refresh_token_deleted', self._on_refresh_token_deleted)

    def _on_refresh_token_created(self, event):
        if not event['mobile']:
            return

        self._service.on_mobile_refresh_token_created(event['user_uuid'])

    def _on_refresh_token_deleted(self, event):
        if not event['mobile']:
            return

        self._service.on_mobile_refresh_token_deleted(event['user_uuid'])
