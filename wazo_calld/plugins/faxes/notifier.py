# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
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

    @staticmethod
    def _build_headers(fax_infos):
        return {'tenant_uuid': fax_infos['tenant_uuid']}

    def notify_fax_created(self, fax_infos):
        user_uuid = fax_infos['user_uuid']
        event = FaxOutboundCreated(fax_infos)
        headers = self._build_headers(fax_infos)
        self._bus_producer.publish(event, headers=headers)

        if user_uuid:
            event = FaxOutboundUserCreated(fax_infos)
            headers[f'user_uuid:{user_uuid}'] = True
            self._bus_producer.publish(event, headers=headers)

    def notify_fax_succeeded(self, fax_infos):
        user_uuid = fax_infos['user_uuid']
        event = FaxOutboundSucceeded(fax_infos)
        headers = self._build_headers(fax_infos)
        self._bus_producer.publish(event, headers=headers)

        if user_uuid:
            event = FaxOutboundUserSucceeded(fax_infos)
            headers[f'user_uuid:{user_uuid}'] = True
            self._bus_producer.publish(event, headers=headers)

    def notify_fax_failed(self, fax_infos):
        user_uuid = fax_infos['user_uuid']
        event = FaxOutboundFailed(fax_infos)
        headers = self._build_headers(fax_infos)
        self._bus_producer.publish(event, headers=headers)

        if user_uuid:
            event = FaxOutboundUserFailed(fax_infos)
            headers[f'user_uuid:{user_uuid}'] = True
            self._bus_producer.publish(event, headers=headers)
