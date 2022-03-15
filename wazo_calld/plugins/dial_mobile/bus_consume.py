# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


class EventHandler:
    def __init__(self, service):
        self._service = service

    def subscribe(self, bus_consumer):
        bus_consumer.on_event('auth_user_sessions_updated', self._on_auth_user_sessions_updated)

    def _on_auth_user_sessions_updated(self, event):
        user_uuid = event['user_uuid']
        has_mobile = False
        for session in event['sessions']:
            if session['mobile']:
                has_mobile = True
                break

        self._service.set_user_hint(user_uuid, has_mobile)
