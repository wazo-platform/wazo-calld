# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_calld.exceptions import APIException


class InvalidCall(APIException):
    def __init__(self, call_id: str, reason: str):
        super().__init__(
            status_code=400,
            message=f'unable to park call: {call_id}, reason={reason}',
            error_id='cannot-park-call',
            details={'call_id': call_id, 'reason': reason},
        )


class NoSuchParkingException(APIException):
    def __init__(self, parking_id: int):
        super().__init__(
            status_code=404,
            message=f'No such parking: id={parking_id}',
            error_id='no-such-parking',
            resource='parking_lots',
            details={
                'parking_id': parking_id,
            },
        )


class NoSuchParkedCall(APIException):
    def __init__(self, tenant_uuid: str, parking_id: int, call_id: str):
        super().__init__(
            status_code=404,
            message=f'No such parked call: parking={parking_id}, call={call_id}',
            error_id='no-such-parked-call',
            resource='parking_lots',
            details={
                'tenant_uuid': tenant_uuid,
                'parking_id': parking_id,
                'call_id': call_id,
            },
        )


class NoSuchCall(APIException):
    def __init__(self, call_id: str):
        super().__init__(
            status_code=404,
            message=f'No such call: {call_id}',
            error_id='no-such-call',
            details={'call_id': call_id},
        )


class ParkingFull(APIException):
    def __init__(self, tenant_uuid: str, parking_id: int, call_id: str):
        super().__init__(
            status_code=503,
            message=f'Unable to park call {call_id}: parking is full',
            error_id='parking-full',
            resource='parking_lots',
            details={
                'tenant_uuid': tenant_uuid,
                'parking_id': parking_id,
                'call_id': call_id,
            },
        )
