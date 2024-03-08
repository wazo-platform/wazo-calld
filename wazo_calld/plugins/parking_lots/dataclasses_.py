# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .helpers import dataclass_from_dict

ChannelStateDesc = Literal[
    'Down',
    'Rsrvd',
    'OffHook',
    'Dialing',
    'Ring',
    'Ringing',
    'Up',
    'Busy',
    'Dialing OffHook',
    'Pre-ring',
    'Unknown',
]


class _FromDictMixin:
    @classmethod
    def from_dict(cls, mapping: dict):
        return dataclass_from_dict(cls, mapping)


@dataclass
class ConfdParkingExtension(_FromDictMixin):
    id: int
    exten: str
    context: str


@dataclass
class ConfdParkingLot(_FromDictMixin):
    id: int
    tenant_uuid: str
    name: str
    slots_start: str
    slots_end: str
    timeout: str
    music_on_hold: str
    extensions: list[ConfdParkingExtension]


@dataclass(frozen=True)
class AsteriskParkedCall(_FromDictMixin):
    parkee_channel: str
    parkee_channel_state: str
    parkee_channel_state_desc: ChannelStateDesc
    parkee_caller_id_num: str
    parkee_caller_id_name: str
    parkee_connected_line_num: str
    parkee_connected_line_name: str
    parkee_language: str
    parkee_account_code: str
    parkee_context: str
    parkee_exten: str
    parkee_priority: str
    parkee_uniqueid: str
    parkee_linkedid: str
    parkee_chan_variable: str
    parker_dial_string: str
    parkinglot: str
    parking_space: str
    parking_timeout: str
    parking_duration: str
