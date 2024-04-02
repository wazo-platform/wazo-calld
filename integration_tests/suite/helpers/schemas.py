# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TypedDict


class ExtensionSchema(TypedDict):
    id: int
    context: str
    exten: str


class ParkingLotSchema(TypedDict):
    id: int
    name: str
    tenant_uuid: str
    slots_start: str
    slots_end: str
    timeout: int
    music_on_hold: str
    extensions: list[ExtensionSchema]
