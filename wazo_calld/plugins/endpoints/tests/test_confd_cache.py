# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import threading
import time
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    equal_to,
    has_entries,
    has_length,
    instance_of,
    less_than,
    none,
    raises,
)

from wazo_calld.plugin_helpers.exceptions import CalldUninitializedError
from wazo_calld.types import StatusDict

from ..bus import EventHandler
from ..notifier import (
    EndpointStatusNotifier,
    LineStatusUpdatedEvent,
    TrunkStatusUpdatedEvent,
)
from ..plugin import Plugin
from ..services import PAGE_PAUSE, Endpoint, NotifyingStatusCache, pages
from .helpers import FakeConfd, line, new_cache, sip_trunk

SERVICES_LOGGER = 'wazo_calld.plugins.endpoints.services'


def http_error(status, body=''):
    response = requests.Response()
    response.status_code = status
    response.reason = body
    return requests.HTTPError(f'{status} {body}', response=response)


def wire(confd):
    """The plugin's wiring, with a fake confd and a recording publisher."""
    cache = new_cache(confd)
    publisher = Mock()
    notifier = EndpointStatusNotifier(publisher, cache)
    ari = Mock()
    ari.endpoints.list.return_value = []
    status_cache = NotifyingStatusCache(notifier.endpoint_updated, ari)
    handler = EventHandler(status_cache, cache)
    return cache, publisher, status_cache, handler


def at_request(confd, kind, offset, action):
    """Run `action` once, just before confd answers the request (kind, offset)."""

    def hook(k, kwargs):
        if k == kind and kwargs['offset'] == offset:
            confd.hooks.remove(hook)
            action()

    confd.hooks.append(hook)


def upper_window(windows):
    """Make tenacity's random wait the top of its window, and record each window.

    Tied to tenacity 8.2.1's layout: `wait_random_exponential` draws through
    `tenacity.wait.random.uniform`.
    """

    def uniform(low, high):
        windows.append((low, high))
        return high

    return patch('tenacity.wait.random.uniform', side_effect=uniform)


def every_handler(handler):
    handler.on_new_channel({'Channel': 'PJSIP/trunk-1-0001', 'Uniqueid': '1'})
    handler.on_hangup({'Channel': 'PJSIP/trunk-1-0001', 'Uniqueid': '1'})
    handler.on_peer_status({'Peer': 'PJSIP/trunk-1', 'PeerStatus': 'Reachable'})
    handler.on_registry(
        {'ChannelType': 'PJSIP', 'Username': 'trunk-1', 'Status': 'Registered'}
    )
    handler.on_registry(
        {'ChannelType': 'IAX2', 'Username': 'iax:u@host', 'Status': 'Registered'}
    )
    handler.on_line_endpoint_deleted({'id': 1})
    handler.on_trunk_endpoint_deleted({'id': 1})
    handler.on_line_edited(
        {'protocol': 'sccp', 'id': 2, 'name': 'l2', 'tenant_uuid': 'tenant'}
    )


class TestPaging(TestCase):
    # criterion 1
    def test_lookups_and_handlers_never_call_confd(self):
        confd = Mock()
        cache, publisher, status_cache, handler = wire(confd)
        status_cache.add_endpoint(Endpoint('PJSIP', 'trunk-1', False, []))

        every_handler(handler)
        cache.get_line('PJSIP', 'line-1')
        cache.get_trunk('PJSIP', 'trunk-1')
        cache.get_trunk_by_id(1)
        cache.get_trunk_by_username('PJSIP', 'u')

        assert_that(confd.mock_calls, equal_to([]))
        publisher.publish.assert_not_called()

    # criterion 1
    def test_builder_lists_always_with_limit_and_offset(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(150)], [line(i) for i in range(5)]
        )

        new_cache(confd).build()

        for _, kwargs in confd.calls:
            assert_that(kwargs, has_entries(recurse=True, limit=100))
            assert 'offset' in kwargs

    # criterion 2
    def test_2500_trunks_then_4600_lines_paged_merged_once_paused(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(2500)], [line(i) for i in range(4600)]
        )
        cache = new_cache(confd)

        cache.build()

        assert_that(confd.offsets('trunks'), equal_to(list(range(0, 2500, 90))))
        assert_that(confd.offsets('lines'), equal_to(list(range(0, 4600, 90))))
        assert_that(
            [kind for kind, _ in confd.calls][27:29], equal_to(['trunks', 'lines'])
        )
        assert_that(cache._loaded, equal_to({'trunks': 2500, 'lines': 4600}))
        assert_that(cache.list_trunks('tenant'), has_length(2500))
        assert_that(cache.list_lines('tenant'), has_length(4600))
        # one pause after every request, so two requests are never back to back
        assert_that(confd.clock.sleeps, equal_to([0.2] * len(confd.calls)))

    # criterion 2
    def test_the_generator_yields_each_item_once_despite_the_overlap(self):
        items = [{'id': i} for i in range(250)]

        def list_fn(limit, offset):
            return {'items': items[offset : offset + limit], 'total': len(items)}

        totals: list = []

        yielded = list(pages(list_fn, totals.append, sleep=lambda seconds: None))

        assert_that(yielded, equal_to(items))
        assert_that(totals, equal_to([250, 250, 250]))

    def test_an_empty_page_ends_the_load(self):
        confd = FakeConfd()

        new_cache(confd).build()

        assert_that(confd.offsets('trunks'), equal_to([0]))
        assert_that(confd.offsets('lines'), equal_to([0]))

    def test_a_short_page_without_total_ends_the_load(self):
        confd = FakeConfd()
        confd.payloads = [
            {'items': [sip_trunk(1)]},
            {'items': [line(1)]},
        ]
        cache = new_cache(confd)

        cache.build()

        assert_that(len(confd.calls), equal_to(2))
        assert_that(cache._loaded, equal_to({'trunks': 1, 'lines': 1}))

    def test_a_confd_ignoring_limit_still_ends_the_load_at_total(self):
        trunks = [sip_trunk(i) for i in range(150)]
        confd = FakeConfd()
        everything = {'items': trunks, 'total': 150}
        confd.payloads = [everything, everything, {'items': [], 'total': 0}]
        cache = new_cache(confd)

        cache.build()

        assert_that(confd.offsets('trunks'), equal_to([0, 90]))
        assert_that(cache._loaded['trunks'], equal_to(150))

    # criterion 3
    def test_an_item_deleted_between_pages_loses_no_other_item(self):
        confd = FakeConfd([], [line(i) for i in range(200)])
        at_request(confd, 'lines', 90, lambda: confd.lines.items.pop(5))
        cache = new_cache(confd)

        cache.build()

        names = {item['name'] for item in cache.list_lines('tenant')}
        assert_that(names, equal_to({f'line-{i}' for i in range(200)}))


class TestResilience(TestCase):
    # criterion 4
    def test_errors_are_retried_on_the_same_offset_through_tenacity(self):
        confd = FakeConfd([], [line(i) for i in range(150)])
        cache = new_cache(confd)
        at_request(
            confd,
            'lines',
            90,
            lambda: confd.errors.extend(
                [
                    requests.ReadTimeout(),
                    requests.ConnectionError(),
                    http_error(401),
                    http_error(500),
                ]
            ),
        )
        windows: list = []

        with upper_window(windows):
            cache.build()

        assert_that(confd.offsets('lines'), equal_to([0, 90, 90, 90, 90, 90]))
        assert_that(windows, equal_to([(0, 1), (0, 2), (0, 4), (0, 8)]))
        retry_sleeps = [s for s in confd.clock.sleeps if s != PAGE_PAUSE]
        assert_that(retry_sleeps, equal_to([1, 2, 4, 8]))
        assert_that(cache._loaded['lines'], equal_to(150))

    # criterion 4
    def test_a_later_page_starts_again_from_the_shortest_wait(self):
        confd = FakeConfd([], [line(i) for i in range(250)])
        cache = new_cache(confd)
        at_request(
            confd, 'lines', 0, lambda: confd.errors.extend([http_error(500)] * 3)
        )
        at_request(confd, 'lines', 90, lambda: confd.errors.append(http_error(500)))
        windows: list = []

        with upper_window(windows):
            cache.build()

        assert_that(windows, equal_to([(0, 1), (0, 2), (0, 4), (0, 1)]))

    # criterion 4
    def test_waits_are_bounded_by_60_seconds(self):
        confd = FakeConfd([], [line(1)])
        confd.errors = [http_error(503)] * 12
        windows: list = []

        with upper_window(windows):
            new_cache(confd).build()

        assert_that(max(high for _, high in windows), equal_to(60))
        assert_that(windows[-1], equal_to((0, 60)))
        assert_that(len(windows), equal_to(12))

    # criterion 4
    def test_a_malformed_page_is_retried_on_the_same_offset(self):
        confd = FakeConfd([], [line(1)])
        confd.payloads = [
            {'items': [], 'total': 0},  # trunks
            {'items': None, 'total': 1},
            {'items': [], 'total': 'one'},
            {'total': 1},
            ['not', 'a', 'page'],
        ]
        cache = new_cache(confd)

        with upper_window([]):
            cache.build()

        assert_that(confd.offsets('lines'), equal_to([0] * 5))
        assert_that(cache.list_lines('tenant'), has_length(1))

    # criterion 5
    def test_an_unreadable_item_is_skipped_and_counted(self):
        no_tenant = line(2)
        del no_tenant['tenant_uuid']
        no_endpoint_name = sip_trunk(3)
        del no_endpoint_name['endpoint_sip']['name']
        confd = FakeConfd(
            [sip_trunk(1), no_endpoint_name], [line(1), no_tenant, 'garbage', line(4)]
        )
        cache = new_cache(confd)

        with self.assertLogs(SERVICES_LOGGER, 'WARNING') as logs:
            cache.build()

        assert_that(cache._skipped, equal_to(3))
        assert_that(cache._loaded, equal_to({'trunks': 1, 'lines': 2}))
        assert_that(
            logs.output[-1],
            equal_to(
                f'WARNING:{SERVICES_LOGGER}:endpoint_cache event=skipped_item skipped=3'
            ),
        )

    # criterion 5
    def test_an_item_with_an_unhashable_id_is_skipped_and_counted(self):
        confd = FakeConfd([], [line(1), {**line(2), 'id': [2]}, line(3)])
        cache = new_cache(confd)

        cache.build()

        assert_that(cache.ready, equal_to(True))
        assert_that(cache._skipped, equal_to(1))
        assert_that(cache._loaded, equal_to({'trunks': 0, 'lines': 2}))

    def test_a_trunk_without_endpoint_is_ignored_not_counted(self):
        confd = FakeConfd([{'id': 1, 'tenant_uuid': 'tenant'}, sip_trunk(2)])
        cache = new_cache(confd)

        cache.build()

        assert_that(cache._skipped, equal_to(0))
        assert_that(cache.list_trunks('tenant'), has_length(1))


class TestEventsBeforeReady(TestCase):
    # criterion 6
    def test_trunk_status_before_trunks_are_ready_is_dropped_without_confd(self):
        confd = FakeConfd([sip_trunk(1, name='trunk-1')])
        cache, publisher, status_cache, handler = wire(confd)
        status_cache.add_endpoint(Endpoint('PJSIP', 'trunk-1', False, []))

        with self.assertLogs('wazo_calld.plugins.endpoints', 'DEBUG') as logs:
            every_handler(handler)

        assert_that(confd.calls, equal_to([]))
        publisher.publish.assert_not_called()
        assert any(
            'dropping status of PJSIP/trunk-1: endpoint cache not loaded yet' in o
            for o in logs.output
        )

    # criterion 6
    def test_an_unknown_registered_username_raises_nothing(self):
        confd = FakeConfd([sip_trunk(1)])
        cache, publisher, _, handler = wire(confd)
        event = {'ChannelType': 'PJSIP', 'Username': 'nobody', 'Status': 'Registered'}

        handler.on_registry(event)
        cache.build()
        handler.on_registry(event)

        publisher.publish.assert_not_called()

    # criterion 7
    def test_once_ready_a_status_change_publishes_as_before(self):
        confd = FakeConfd(
            [sip_trunk(1, name='trunk-1', username='u1')], [line(10, name='line-10')]
        )
        cache, publisher, status_cache, handler = wire(confd)
        status_cache.add_endpoint(Endpoint('PJSIP', 'trunk-1', False, []))
        status_cache.add_endpoint(Endpoint('PJSIP', 'line-10', False, []))
        cache.build()

        handler.on_registry(
            {'ChannelType': 'PJSIP', 'Username': 'u1', 'Status': 'Registered'}
        )
        handler.on_new_channel({'Channel': 'PJSIP/line-10-0001', 'Uniqueid': '7'})

        assert_that(
            [c.args[0] for c in publisher.publish.call_args_list],
            contains_exactly(
                TrunkStatusUpdatedEvent(1, 'sip', 'trunk-1', True, 0, 'tenant'),
                LineStatusUpdatedEvent(10, 'sip', 'line-10', False, 1, 'tenant'),
            ),
        )

    # criterion 7: trunks load first, a trunk publishes while lines still load
    def test_a_trunk_publishes_while_lines_load(self):
        confd = FakeConfd([sip_trunk(1, name='trunk-1')], [line(10)])
        cache, publisher, status_cache, handler = wire(confd)
        status_cache.add_endpoint(Endpoint('PJSIP', 'trunk-1', False, []))
        at_request(
            confd,
            'lines',
            0,
            lambda: handler.on_new_channel(
                {'Channel': 'PJSIP/trunk-1-0001', 'Uniqueid': '1'}
            ),
        )

        cache.build()

        publisher.publish.assert_called_once_with(
            TrunkStatusUpdatedEvent(1, 'sip', 'trunk-1', False, 1, 'tenant')
        )


class TestEventsWinOverPages(TestCase):
    # criterion 8
    def test_line_events_during_build_win_over_later_pages(self):
        lines = [line(i) for i in range(200)]
        lines[150] = line(150, name='old-150', protocol='sccp')
        confd = FakeConfd([], lines)
        cache, _, _, handler = wire(confd)

        def events():
            handler.on_line_endpoint_deleted({'id': 120})
            handler.on_line_edited(
                {
                    'protocol': 'sccp',
                    'id': 150,
                    'name': 'new-150',
                    'tenant_uuid': 'tenant',
                }
            )

        at_request(confd, 'lines', 90, events)

        cache.build()

        names = {item['name'] for item in cache.list_lines('tenant')}
        assert 'line-120' not in names
        assert 'old-150' not in names
        assert 'new-150' in names
        assert_that(names, has_length(199))
        assert_that(cache._touched, equal_to({'trunks': set(), 'lines': set()}))

    # criterion 8
    def test_trunk_events_during_build_win_over_later_pages(self):
        trunks = [sip_trunk(i) for i in range(200)]
        confd = FakeConfd(trunks)
        cache, _, _, handler = wire(confd)

        def events():
            handler.on_trunk_endpoint_deleted({'id': 120})
            handler.on_endpoint_sip_updated(
                {
                    'trunk': {'id': 150},
                    'line': None,
                    'name': 'renamed-150',
                    'tenant_uuid': 'tenant',
                    'registration_section_options': [['client_uri', 'u150']],
                }
            )

        at_request(confd, 'trunks', 90, events)

        cache.build()

        assert_that(cache.get_trunk_by_id(120), none())
        assert_that(cache.get_trunk('PJSIP', 'trunk-150'), none())
        assert_that(cache.get_trunk_by_id(150), has_entries(name='renamed-150'))
        assert_that(cache.get_trunk_by_username('PJSIP', 'u150'), has_entries(id=150))

    # criterion 8
    def test_a_line_deleted_then_re_added_during_build_keeps_the_new_row(self):
        lines = [line(i) for i in range(200)]
        lines[150] = line(150, name='old-150')
        confd = FakeConfd([], lines)
        cache, _, _, handler = wire(confd)

        def events():
            handler.on_line_endpoint_deleted({'id': 150})
            cache.add_line('sip', 150, 'new-150', None, 'tenant')

        at_request(confd, 'lines', 90, events)

        cache.build()

        names = {item['name'] for item in cache.list_lines('tenant')}
        assert 'old-150' not in names
        assert_that(cache.get_line('PJSIP', 'new-150'), has_entries(id=150))
        assert_that(names, has_length(200))

    def test_after_the_build_an_event_is_not_remembered(self):
        confd = FakeConfd([], [line(1)])
        cache = new_cache(confd)
        cache.build()

        cache.delete_line(1)

        assert_that(cache._touched, equal_to({'trunks': set(), 'lines': set()}))


class TestTimingAndConcurrency(TestCase):
    # criterion 9
    def test_4600_lines_at_1_5_seconds_a_page(self):
        confd = FakeConfd([], [line(i) for i in range(4600)], page_cost=1.5)
        cache = new_cache(confd)
        started = confd.clock.now

        cache.build()

        assert_that(len(confd.offsets('lines')), equal_to(52))
        # one trunk page (empty) plus 52 line pages, each followed by its pause
        assert_that(round(confd.clock.now - started, 1), equal_to(round(53 * 1.7, 1)))

    # criterion 9
    def test_no_bus_handler_waits_on_a_slow_confd(self):
        released = threading.Event()
        entered = threading.Event()
        confd = FakeConfd([sip_trunk(1, name='trunk-1')], [line(1, name='line-1')])

        def block(kind, kwargs):
            entered.set()
            released.wait(5)

        confd.hooks.append(block)
        cache, publisher, status_cache, handler = wire(confd)
        status_cache.add_endpoint(Endpoint('PJSIP', 'trunk-1', False, []))
        builder = threading.Thread(target=cache.build)
        builder.start()
        try:
            assert entered.wait(5)
            started = time.monotonic()
            for i in range(50):
                handler.on_new_channel(
                    {'Channel': 'PJSIP/trunk-1-0001', 'Uniqueid': str(i)}
                )
                handler.on_registry(
                    {'ChannelType': 'PJSIP', 'Username': 'x', 'Status': 'Registered'}
                )
            elapsed = time.monotonic() - started
        finally:
            released.set()
            builder.join(5)

        assert_that(elapsed, less_than(1.0))
        assert_that(len(confd.calls), equal_to(2))

    # criterion 10
    def test_lists_raise_uninitialized_until_their_index_is_ready(self):
        confd = FakeConfd([sip_trunk(1)], [line(1)])
        cache = new_cache(confd)
        seen = {}

        def while_lines_load():
            seen['trunks'] = cache.list_trunks('tenant')
            try:
                cache.list_lines('tenant')
            except CalldUninitializedError as e:
                seen['lines'] = e

        assert_that(
            calling(cache.list_trunks).with_args('tenant'),
            raises(CalldUninitializedError),
        )
        at_request(confd, 'lines', 0, while_lines_load)

        cache.build()

        assert_that(seen['trunks'], has_length(1))
        assert_that(seen['lines'], instance_of(CalldUninitializedError))
        assert_that(cache.list_lines('tenant'), has_length(1))

    # criterion 10
    def test_iterating_while_the_builder_writes_raises_nothing(self):
        confd = FakeConfd([], [line(i) for i in range(20000)])
        cache = new_cache(confd)
        cache._sleep = lambda seconds: None
        errors: list[Exception] = []

        def reader():
            while builder.is_alive():
                try:
                    cache.delete_line(-1)
                    cache.get_trunk_by_id(-1)
                except Exception as e:  # pragma: no cover - the failure we test for
                    errors.append(e)
                    return

        interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)  # switch threads as often as possible
        try:
            builder = threading.Thread(target=cache.build)
            builder.start()
            readers = [threading.Thread(target=reader) for _ in range(2)]
            for r in readers:
                r.start()
            builder.join(30)
            for r in readers:
                r.join(30)
        finally:
            sys.setswitchinterval(interval)

        assert_that(errors, equal_to([]))
        assert_that(cache.list_lines('tenant'), has_length(20000))

    # criterion 10
    def test_listing_while_events_write_raises_nothing(self):
        confd = FakeConfd([sip_trunk(i) for i in range(2000)], [])
        cache = new_cache(confd)
        cache.build()
        errors: list[Exception] = []
        done = threading.Event()

        def writer():
            for i in range(2000, 22000):
                cache.add_line('sip', i, f'line-{i}', None, 'tenant')
                cache.add_trunk('sip', i, f'trunk-{i}', None, 'tenant')
            done.set()

        def reader():
            while not done.is_set():
                try:
                    cache.list_lines('tenant')
                    cache.list_trunks('tenant')
                except Exception as e:  # pragma: no cover - the failure we test for
                    errors.append(e)
                    return

        interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)  # switch threads as often as possible
        try:
            threads = [threading.Thread(target=writer)]
            threads += [threading.Thread(target=reader) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
        finally:
            sys.setswitchinterval(interval)

        assert_that(errors, equal_to([]))
        assert_that(cache.list_trunks('tenant'), has_length(22000))


class TestObservability(TestCase):
    # criterion 11
    def test_status_fails_until_both_indexes_are_ready(self):
        confd = FakeConfd([sip_trunk(1)], [line(1)])
        cache = new_cache(confd)
        plugin = Plugin()
        plugin._confd_cache = cache
        plugin._async_tasks_completed = True
        snapshots = []

        def snapshot():
            status: StatusDict = {'plugins': {'endpoints': {}}}
            plugin._provide_status(status)
            snapshots.append(status['plugins']['endpoints'])

        snapshot()
        at_request(confd, 'trunks', 0, snapshot)
        at_request(confd, 'lines', 0, snapshot)
        cache.build()
        snapshot()

        assert_that(
            [s['status'] for s in snapshots], equal_to(['fail', 'fail', 'fail', 'ok'])
        )
        assert_that(snapshots[-1], equal_to({'status': 'ok'}))

    # criterion 11
    def test_status_fails_while_ari_is_not_initialized(self):
        confd = FakeConfd()
        cache = new_cache(confd)
        cache.build()
        plugin = Plugin()
        plugin._confd_cache = cache
        plugin._async_tasks_completed = False
        status: StatusDict = {'plugins': {'endpoints': {}}}

        plugin._provide_status(status)

        assert_that(status['plugins']['endpoints']['status'], equal_to('fail'))

    # criterion 12
    def test_the_last_log_line_reads_the_totals(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(3)], [line(i) for i in range(4600)]
        )
        confd.errors = [requests.ReadTimeout()]
        cache = new_cache(confd)

        with upper_window([]), self.assertLogs(SERVICES_LOGGER, 'DEBUG') as logs:
            cache.build()

        messages = [record.getMessage() for record in logs.records]
        for message in messages:
            assert message.startswith('endpoint_cache '), message
        # 1 s retry, 53 pauses of 0.2 s
        assert_that(
            messages[-1],
            equal_to(
                'endpoint_cache state=ready lines=4600 trunks=3 seconds=11.6 pages=53'
            ),
        )
        assert_that(
            messages[0],
            equal_to(
                'endpoint_cache event=retry offset=0 error=ReadTimeout status=None'
                ' attempt=1 retry_in=1.0'
            ),
        )
        assert any(
            m == 'endpoint_cache state=loading_lines pages=10 loaded=820 total=4600'
            for m in messages
        )

    # criterion 12
    def test_an_error_body_never_reaches_a_log_line(self):
        confd = FakeConfd()
        confd.errors = [http_error(500, 'secret-token-xyz')]

        with upper_window([]), self.assertLogs(SERVICES_LOGGER, 'DEBUG') as logs:
            new_cache(confd).build()

        assert_that(
            logs.records[0].getMessage(),
            equal_to(
                'endpoint_cache event=retry offset=0 error=HTTPError status=500'
                ' attempt=1 retry_in=1.0'
            ),
        )
        for record in logs.records:
            assert 'secret-token-xyz' not in record.getMessage()

    # criterion 13
    def test_a_second_token_starts_no_second_build(self):
        cache = new_cache(FakeConfd())
        cache.build = Mock()

        cache.start('token-1')
        first = cache._thread
        cache.start('token-2')
        first.join(5)

        assert_that(cache._thread, equal_to(first))
        cache.build.assert_called_once_with()
        assert_that(first.daemon, equal_to(True))


class TestTrunkIndex(TestCase):
    def test_trunks_are_found_by_id_name_and_registration_username(self):
        no_client_uri = sip_trunk(2)
        no_client_uri['endpoint_sip']['registration_section_options'] = []
        iax = {'id': 3, 'tenant_uuid': 'tenant', 'endpoint_iax': {'name': 'iax-3'}}
        custom = {
            'id': 4,
            'tenant_uuid': 'tenant',
            'endpoint_custom': {'interface': 'dahdi/1'},
        }
        confd = FakeConfd(
            [sip_trunk(1, name='t1', username='u1'), no_client_uri, iax, custom]
        )
        cache = new_cache(confd)
        cache.build()

        assert_that(cache.get_trunk_by_id(1), has_entries(name='t1'))
        assert_that(cache.get_trunk_by_id(5), none())
        assert_that(cache.get_trunk('PJSIP', 'trunk-2'), has_entries(id=2))
        assert_that(cache.get_trunk_by_username('PJSIP', 'u1'), has_entries(id=1))
        assert_that(cache.get_trunk_by_username('PJSIP', None), none())
        assert_that(cache.get_trunk_by_username('IAX2', 'iax-3'), has_entries(id=3))
        assert_that(cache.get_trunk('custom', 'dahdi/1'), has_entries(id=4))


class TestPluginWiring(TestCase):
    # criteria 11 and 13: the build starts on a token, and /status reads it
    def test_load_starts_the_build_on_a_token_and_reports_its_status(self):
        token_changed_subscribe = Mock()
        status_aggregator = Mock()
        dependencies = {
            'api': Mock(),
            'ari': Mock(),
            'config': {'confd': {}},
            'status_aggregator': status_aggregator,
            'token_changed_subscribe': token_changed_subscribe,
            'bus_consumer': Mock(),
            'bus_publisher': Mock(),
        }
        plugin = Plugin()

        with patch('wazo_calld.plugins.endpoints.plugin.ConfdClient') as client:
            plugin.load(dependencies)  # type: ignore[arg-type]

        subscribed = [c.args[0] for c in token_changed_subscribe.call_args_list]
        assert_that(
            subscribed,
            equal_to([client.return_value.set_token, plugin._confd_cache.start]),
        )
        provider = status_aggregator.add_provider.call_args.args[0]
        status: StatusDict = {'plugins': {'endpoints': {}}}
        provider(status)
        assert_that(status['plugins']['endpoints'], equal_to({'status': 'fail'}))
