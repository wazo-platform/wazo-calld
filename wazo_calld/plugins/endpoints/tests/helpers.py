# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ..services import ConfdCache

MAX_REQUESTS = 2000  # a build that never ends fails the test instead of hanging it


class EndlessBuild(BaseException):
    """Not an Exception: the builder retries every Exception, this one escapes it."""


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0
        self.wall_offset = 0.0  # an NTP step moves the wall clock only
        self.sleeps = []

    def time(self):
        return self.now + self.wall_offset

    def monotonic(self):
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
        self.ignores_paging = False

    def list(self, **kwargs):
        self._confd.calls.append((self.kind, kwargs))
        if len(self._confd.calls) > MAX_REQUESTS:
            raise EndlessBuild(f'more than {MAX_REQUESTS} requests')
        self._confd.before_answer(self.kind, kwargs)
        if self._confd.errors:
            raise self._confd.errors.pop(0)
        self._confd.clock.now += self._confd.page_cost
        if self._confd.payloads:
            return self._confd.payloads.pop(0)
        if self.ignores_paging:
            return {'items': list(self.items), 'total': len(self.items)}
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
        monotonic=confd.clock.monotonic,
        sleep=confd.clock.sleep,
        jitter=lambda low, high: 1.0,
    )
