# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ..services import ConfdCache


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeResource:
    """A confd list resource answering pages the way confd does (limit, offset, total)."""

    def __init__(self, kind, items, confd):
        self.kind = kind
        self.items = items
        self._confd = confd

    def list(self, **kwargs):
        self._confd.calls.append((self.kind, kwargs))
        self._confd.before_answer(self.kind, kwargs)
        if self._confd.errors:
            raise self._confd.errors.pop(0)
        self._confd.clock.now += self._confd.page_cost
        if self._confd.payloads:
            return self._confd.payloads.pop(0)
        offset = kwargs['offset']
        limit = kwargs['limit']
        return {
            'items': self.items[offset : offset + limit],
            'total': len(self.items),
        }


class FakeConfd:
    def __init__(self, trunks=(), lines=(), clock=None, page_cost=0.0):
        self.clock = clock or FakeClock()
        self.page_cost = page_cost
        self.calls = []
        self.errors = []
        self.payloads = []
        self.hooks = []
        self.trunks = FakeResource('trunks', list(trunks), self)
        self.lines = FakeResource('lines', list(lines), self)

    def before_answer(self, kind, kwargs):
        for hook in list(self.hooks):
            hook(kind, kwargs)

    def offsets(self, kind):
        return [kwargs['offset'] for k, kwargs in self.calls if k == kind]


def sip_trunk(trunk_id, name=None, username=None, tenant_uuid='tenant'):
    name = name or f'trunk-{trunk_id}'
    return {
        'id': trunk_id,
        'tenant_uuid': tenant_uuid,
        'endpoint_sip': {
            'name': name,
            'registration_section_options': [['client_uri', username or name]],
        },
    }


def line(line_id, name=None, protocol='sip', tenant_uuid='tenant'):
    return {
        'id': line_id,
        'name': name or f'line-{line_id}',
        'protocol': protocol,
        'tenant_uuid': tenant_uuid,
    }


def new_cache(confd):
    return ConfdCache(
        confd,
        clock=confd.clock.time,
        sleep=confd.clock.sleep,
        jitter=lambda low, high: 1.0,
    )
