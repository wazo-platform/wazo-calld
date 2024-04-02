# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
from dataclasses import is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from inspect import signature
from typing import Any, TypeVar, get_args, get_origin, get_type_hints


class DontCheckTenant(Enum):
    DONT_CHECK_TENANT = auto()


DONT_CHECK_TENANT = DontCheckTenant.DONT_CHECK_TENANT

T = TypeVar('T')

_CAMEL_TO_SNAKE = (
    re.compile(r'(.)([A-Z][a-z]+)'),
    re.compile(r'__([A-Z])'),
    re.compile(r'([a-z0-9])([A-Z])'),
)


def camel_to_snake(name: str) -> str:
    '''Helper function to convert CamelCase to snake_case'''
    name = _CAMEL_TO_SNAKE[0].sub(r'\1_\2', name)
    name = _CAMEL_TO_SNAKE[1].sub(r'_\1', name)
    name = _CAMEL_TO_SNAKE[2].sub(r'\1_\2', name)
    return name.lower()


def snakify_keys(dict_: dict[str, Any]) -> dict[str, Any]:
    '''Helper to convert CamelCase to snake_case'''
    return {camel_to_snake(k) if k[0].isupper() else k: v for k, v in dict_.items()}


def dataclass_from_dict(dataclass: type[T], dict_: dict) -> T:
    '''Helper to recursively instanciate a dataclass while ignoring unknown parameters'''
    dict_ = snakify_keys(dict_)
    valid_props = signature(dataclass).parameters
    hints: dict[str, type] = get_type_hints(dataclass)
    args = {}

    for key, value in dict_.items():
        if key not in valid_props:
            continue

        type_ = hints[key]
        if get_origin(type_) in (list, set, tuple):
            if is_dataclass(nested_type := get_args(type_)[0]):
                args[key] = type_(
                    [dataclass_from_dict(nested_type, item) for item in value]
                )
                continue
            args[key] = type_(value)
        elif is_dataclass(type_):
            args[key] = dataclass_from_dict(type_, value)
        else:
            args[key] = value

    return dataclass(**args)


def split_parking_id_from_name(parking_name: str) -> int:
    prefix, *id_ = parking_name.split('-', 1)
    if not id_ or prefix != 'parkinglot':
        raise ValueError('invalid parking lot name')
    return int(id_.pop(0))


def timestamp(seconds: int | str) -> str | None:
    '''Helper to convert seconds to a timestamp'''
    if not (value := int(seconds or 0)):
        return None

    now = datetime.now(timezone.utc)

    try:
        timestamp = now + timedelta(seconds=value)
    except OverflowError:
        return None
    return timestamp.replace(microsecond=0).isoformat()


def timestamp_since(seconds_ago: int | str) -> str:
    '''Helper to convert seconds to a timestamp in the past'''
    value = abs(int(seconds_ago or 0))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = now - timedelta(seconds=value)
    return timestamp.isoformat()
