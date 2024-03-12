# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from flask import request
from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schemas import (
    ParkingLotSchema,
    park_call_request_schema,
    parked_call_put_response_schema,
)
from .services import ParkingService


class _Base(AuthResource):
    def __init__(self, parking_service: ParkingService):
        self._service = parking_service


class ParkingLotResource(_Base):
    @required_acl('calld.parkings.{parking_id}.read')
    def get(self, parking_id: int) -> tuple[dict, int]:
        tenant = Tenant.autodetect()
        parking_lot = self._service.get_parking(tenant.uuid, parking_id)
        calls = self._service.list_parked_calls(tenant.uuid, parking_id)

        return ParkingLotSchema(context={'calls': calls}).dump(parking_lot), 200


class ParkCallResource(_Base):
    @required_acl('calld.calls.{call_id}.park.update')
    def put(self, call_id: str):
        tenant = Tenant.autodetect()
        request_data = park_call_request_schema.load(request.get_json(force=True))

        parked_call = self._service.park_call(
            request_data.pop('parking_id'), call_id, tenant.uuid, **request_data
        )

        return parked_call_put_response_schema.dump(parked_call), 200


class UserCallParkResource(_Base):
    @required_acl('calld.users.me.calls.{call_id}.park.update')
    def put(self, call_id: str):
        request_data = park_call_request_schema.load(request.get_json(force=True))

        parked_call = self._service.park_collocutor_call(
            request.user_uuid, request_data.pop('parking_id'), call_id, **request_data
        )
        return parked_call_put_response_schema.dump(parked_call), 200
