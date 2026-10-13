# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
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
    none,
    not_,
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
from ..services import Endpoint, NotifyingStatusCache
from .helpers import FakeClock, FakeConfd, line, new_cache, sip_trunk


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
    cache.on_ready(handler.replay_registry)
    cache.on_ready(notifier.replay)
    return cache, publisher, status_cache, handler


def at_request(confd, kind, offset, action):
    """Run `action` once, just before confd answers the request (kind, offset)."""

    def hook(k, kwargs):
        if k == kind and kwargs['offset'] == offset:
            confd.hooks.remove(hook)
            action()

    confd.hooks.append(hook)


class TestBuilderPaging(TestCase):
    # criterion 1
    def test_lookups_and_handlers_never_call_confd(self):
        confd = Mock()
        cache = new_cache(confd)
        publisher = Mock()
        notifier = EndpointStatusNotifier(publisher, cache)
        status_cache = NotifyingStatusCache(notifier.endpoint_updated, Mock())
        status_cache.add_endpoint(Endpoint('PJSIP', 'abc', False, []))
        handler = EventHandler(status_cache, cache)

        cache.get_line('PJSIP', 'abc')
        cache.get_trunk('PJSIP', 'abc')
        cache.get_trunk_by_id(1)
        cache.get_trunk_by_username('PJSIP', 'abc')
        handler.on_new_channel({'Channel': 'PJSIP/abc-0001', 'Uniqueid': '1'})
        handler.on_hangup({'Channel': 'PJSIP/abc-0001', 'Uniqueid': '1'})
        handler.on_peer_status({'Peer': 'PJSIP/abc', 'PeerStatus': 'Reachable'})
        handler.on_registry(
            {'ChannelType': 'PJSIP', 'Username': 'abc', 'Status': 'Registered'}
        )
        handler.on_line_endpoint_deleted({'id': 1})
        handler.on_trunk_endpoint_deleted({'id': 1})

        assert_that(confd.mock_calls, equal_to([]))
        publisher.publish.assert_not_called()

    # criterion 1
    def test_builder_lists_always_with_limit_and_offset(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(150)], [line(i) for i in range(5)]
        )

        new_cache(confd).build()

        assert_that(
            [kwargs for _, kwargs in confd.calls],
            contains_exactly(
                {'recurse': True, 'limit': 100, 'offset': 0},
                {'recurse': True, 'limit': 100, 'offset': 90},
                {'recurse': True, 'limit': 100, 'offset': 0},
            ),
        )

    # criterion 2
    def test_2500_trunks_then_4600_lines_paged_merged_once_paused(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(2500)], [line(i) for i in range(4600)]
        )
        cache = new_cache(confd)

        cache.build()

        assert_that([k for k, _ in confd.calls[:28]], equal_to(['trunks'] * 28))
        assert_that(confd.offsets('trunks'), equal_to(list(range(0, 2500, 90))))
        assert_that(confd.offsets('lines'), equal_to(list(range(0, 4600, 90))))
        requests_made = len(confd.calls)
        assert_that(confd.clock.sleeps, equal_to([0.2] * (requests_made - 1)))
        assert_that(cache.list_trunks('tenant'), has_length(2500))
        assert_that(cache.list_lines('tenant'), has_length(4600))
        assert_that(
            cache.status(),
            has_entries(
                trunks_loaded=2500,
                trunks_total=2500,
                lines_loaded=4600,
                lines_total=4600,
                pages=requests_made,
            ),
        )

    # criterion 2: an empty page ends the load even if total says otherwise
    def test_an_empty_page_ends_the_load(self):
        confd = FakeConfd([], [line(1)])
        confd.payloads = [
            {'items': [], 'total': 0},
            {'items': [line(i) for i in range(100)], 'total': 500},
            {'items': [], 'total': 500},
        ]
        cache = new_cache(confd)

        cache.build()

        assert_that(confd.offsets('lines'), equal_to([0, 90]))
        assert_that(cache.lines_ready, equal_to(True))

    # criterion 2: a short page is the last one, total or not
    def test_a_short_page_without_total_ends_the_load(self):
        confd = FakeConfd()
        confd.payloads = [
            {'items': [sip_trunk(1)]},
            {'items': [line(1), line(2)], 'total': 500},
        ]
        cache = new_cache(confd)

        cache.build()

        assert_that(confd.offsets('trunks'), equal_to([0]))
        assert_that(confd.offsets('lines'), equal_to([0]))
        assert_that(cache.list_lines('tenant'), has_length(2))
        assert_that(cache.status(), has_entries(trunks_total=None, lines_total=500))

    # criterion 2: merged once each
    def test_an_item_seen_again_in_the_overlap_is_not_merged_twice(self):
        lines = [line(i) for i in range(150)]
        confd = FakeConfd([], lines)

        def rename_95():
            confd.lines.items[95] = line(95, name='renamed-95')

        at_request(confd, 'lines', 90, rename_95)
        cache = new_cache(confd)

        cache.build()

        # the rename reaches calld through its sip_endpoint_updated event
        assert_that(cache.list_lines('tenant'), has_length(150))
        assert_that(cache.get_line('PJSIP', 'renamed-95'), none())

    # criterion 3
    def test_an_item_deleted_between_pages_loses_no_other_item(self):
        lines = [line(i) for i in range(300)]
        confd = FakeConfd([], lines)
        at_request(confd, 'lines', 90, lambda: confd.lines.items.pop(5))
        cache = new_cache(confd)

        cache.build()

        # line 5 was loaded before it went; its line_deleted event removes it
        ids = sorted(item['id'] for item in cache.list_lines('tenant'))
        assert_that(ids, equal_to(list(range(300))))


class TestBuilderResilience(TestCase):
    def setUp(self):
        self.confd = FakeConfd([sip_trunk(1)], [line(i) for i in range(150)])
        self.jitter = Mock(return_value=1.0)
        self.cache = new_cache(self.confd)
        self.cache._jitter = self.jitter

    # criterion 4
    def test_errors_are_retried_with_doubling_backoff_on_the_same_request(self):
        self.confd.errors = [
            requests.ReadTimeout(),
            requests.ConnectionError(),
            http_error(401),
            http_error(500),
        ]

        self.cache.build()

        assert_that(self.confd.clock.sleeps[:4], equal_to([1.0, 2.0, 4.0, 8.0]))
        assert_that(self.confd.offsets('trunks'), equal_to([0] * 5))
        assert_that(self.cache.lines_ready, equal_to(True))
        assert_that(self.cache.status(), has_entries(retries=4, consecutive_failures=0))

    # criterion 4
    def test_backoff_resets_after_a_success(self):
        at_request(
            self.confd,
            'lines',
            90,
            lambda: self.confd.errors.extend([http_error(500), http_error(500)]),
        )
        at_request(
            self.confd,
            'lines',
            0,
            lambda: self.confd.errors.append(http_error(500)),
        )

        self.cache.build()

        # trunks 0, pause, lines 0 fails (1 s), lines 0, pause, lines 90 fails twice
        assert_that(self.confd.clock.sleeps, equal_to([0.2, 1.0, 0.2, 1.0, 2.0]))

    # criterion 4
    def test_backoff_caps_at_60_seconds_with_20_percent_jitter(self):
        self.confd.errors = [http_error(503) for _ in range(9)]
        self.jitter.return_value = 1.2

        self.cache.build()

        assert_that(
            self.confd.clock.sleeps[:9],
            equal_to([1.2, 2.4, 4.8, 9.6, 19.2, 38.4, 60.0, 60.0, 60.0]),
        )
        self.jitter.assert_called_with(0.8, 1.2)

    # criterion 4
    def test_backoff_after_days_of_failures_stays_at_the_cap(self):
        self.cache._failures = 5000
        self.confd.errors = [http_error(503)]

        self.cache.build()

        assert_that(self.confd.clock.sleeps[0], equal_to(60.0))

    # criterion 4
    def test_jitter_below_one_shortens_the_delay(self):
        self.confd.errors = [http_error(503)]
        self.jitter.return_value = 0.8

        self.cache.build()

        assert_that(self.confd.clock.sleeps[0], equal_to(0.8))

    # criterion 5
    def test_an_unreadable_item_is_skipped_and_counted(self):
        self.confd.lines.items[3] = {'id': 3, 'name': 'no-protocol'}
        self.confd.trunks.items.append(
            {'id': 9, 'endpoint_sip': {'name': 'no-options'}}
        )

        self.cache.build()

        ids = sorted(item['id'] for item in self.cache.list_lines('tenant'))
        assert_that(ids, equal_to([i for i in range(150) if i != 3]))
        assert_that(self.cache.status(), has_entries(skipped_items=2))

    # criterion 5
    def test_an_odd_payload_is_retried_not_fatal(self):
        self.confd.payloads = [
            {'items': None, 'total': 1},
            'garbage',
            {'total': 1},
            {'items': [], 'total': 'one'},
        ]

        self.cache.build()

        assert_that(self.confd.offsets('trunks'), equal_to([0] * 5))
        assert_that(self.cache.lines_ready, equal_to(True))
        assert_that(self.cache.status(), has_entries(retries=4))

    # criterion 5
    def test_a_failing_ready_callback_does_not_stop_the_builder(self):
        self.cache.on_ready(Mock(side_effect=RuntimeError('boom')))

        self.cache.build()

        assert_that(self.cache.lines_ready, equal_to(True))


class TestHeldNotifications(TestCase):
    def setUp(self):
        self.confd = FakeConfd(
            [sip_trunk(1, name='trunk-1')],
            [line(10, name='line-10'), line(11, name='line-11')],
        )
        self.cache, self.publisher, self.status, self.handler = wire(self.confd)
        self.status.add_endpoint(Endpoint('PJSIP', 'line-10', False, []))
        self.status.add_endpoint(Endpoint('PJSIP', 'trunk-1', False, []))

    def _channel(self, name, unique_id):
        return {'Channel': f'PJSIP/{name}-0001', 'Uniqueid': unique_id}

    # criterion 6
    def test_three_changes_while_lines_load_publish_once_the_latest(self):
        def three_changes():
            self.handler.on_new_channel(self._channel('line-10', '1'))
            self.handler.on_new_channel(self._channel('line-10', '2'))
            self.handler.on_peer_status(
                {'Peer': 'PJSIP/line-10', 'PeerStatus': 'Reachable'}
            )
            assert_that(self.cache.status(), has_entries(held_notifications=1))
            self.publisher.publish.assert_not_called()

        at_request(self.confd, 'lines', 0, three_changes)

        self.cache.build()

        self.publisher.publish.assert_called_once_with(
            LineStatusUpdatedEvent(10, 'sip', 'line-10', True, 2, 'tenant')
        )
        assert_that(self.cache.status(), has_entries(held_notifications=0))

    # criterion 7
    def test_a_held_notification_for_a_line_deleted_during_build_is_dropped(self):
        def change_then_delete():
            self.handler.on_new_channel(self._channel('line-10', '1'))
            self.handler.on_line_endpoint_deleted({'id': 10})

        at_request(self.confd, 'lines', 0, change_then_delete)

        self.cache.build()

        self.publisher.publish.assert_not_called()
        assert_that(self.cache.get_line('PJSIP', 'line-10'), none())

    # criterion 8
    def test_trunk_events_before_trunks_are_ready_are_held_then_published(self):
        published_while_lines_load = []

        def trunk_events():
            self.handler.on_new_channel(self._channel('trunk-1', '1'))
            self.handler.on_hangup(self._channel('trunk-1', '1'))
            self.handler.on_peer_status(
                {'Peer': 'PJSIP/trunk-1', 'PeerStatus': 'Reachable'}
            )

        at_request(self.confd, 'trunks', 0, trunk_events)
        at_request(
            self.confd,
            'lines',
            0,
            lambda: published_while_lines_load.extend(
                self.publisher.publish.call_args_list
            ),
        )

        self.cache.build()

        assert_that(len(self.confd.calls), equal_to(2))
        assert_that(
            [c.args[0] for c in published_while_lines_load],
            contains_exactly(
                TrunkStatusUpdatedEvent(1, 'sip', 'trunk-1', True, 0, 'tenant')
            ),
        )

    # criterion 8
    def test_registry_before_trunks_are_ready_is_held_then_replayed(self):
        registry = {
            'ChannelType': 'PJSIP',
            'Username': 'trunk-1',
            'Status': 'Registered',
        }
        at_request(self.confd, 'trunks', 0, lambda: self.handler.on_registry(registry))
        registered_while_lines_load = []
        at_request(
            self.confd,
            'lines',
            0,
            lambda: registered_while_lines_load.append(
                self.status.get('PJSIP', 'trunk-1').registered
            ),
        )

        self.cache.build()

        assert_that(registered_while_lines_load, equal_to([True]))
        self.publisher.publish.assert_called_once_with(
            TrunkStatusUpdatedEvent(1, 'sip', 'trunk-1', True, 0, 'tenant')
        )

    # criterion 8
    def test_unknown_registered_username_raises_nothing(self):
        self.cache.build()
        registry = {
            'ChannelType': 'PJSIP',
            'Username': 'nobody',
            'Status': 'Registered',
        }

        assert_that(
            calling(self.handler.on_registry).with_args(registry),
            not_(raises(Exception)),
        )

    def test_unknown_endpoint_after_build_is_dropped(self):
        self.cache.build()
        self.status.add_endpoint(Endpoint('PJSIP', 'stranger', False, []))

        self.handler.on_new_channel(self._channel('stranger', '1'))

        self.publisher.publish.assert_not_called()
        assert_that(self.cache.status(), has_entries(held_notifications=0))

    # criterion 11
    def test_line_events_during_build_win_over_later_pages(self):
        def events():
            self.handler.on_line_endpoint_deleted({'id': 10})
            self.handler.on_line_edited(
                {
                    'id': 11,
                    'protocol': 'sccp',
                    'name': 'renamed',
                    'tenant_uuid': 'tenant',
                }
            )

        at_request(self.confd, 'lines', 0, events)

        self.cache.build()

        assert_that(self.cache.get_line('PJSIP', 'line-10'), none())
        assert_that(self.cache.get_line('PJSIP', 'line-11'), none())
        assert_that(
            self.cache.get_line('SCCP', 'renamed'), has_entries(id=11, name='renamed')
        )
        assert_that(self.cache.list_lines('tenant'), has_length(1))

    # criterion 11
    def test_trunk_events_during_build_win_over_later_pages(self):
        at_request(
            self.confd,
            'trunks',
            0,
            lambda: self.handler.on_trunk_endpoint_deleted({'id': 1}),
        )

        self.cache.build()

        assert_that(self.cache.list_trunks('tenant'), has_length(0))


class TestTimingAndConcurrency(TestCase):
    # criterion 9
    def test_4600_lines_at_1_5_seconds_a_page(self):
        clock = FakeClock()
        confd = FakeConfd([], [line(i) for i in range(4600)], clock, page_cost=1.5)
        cache = new_cache(confd)
        start = clock.now

        cache.build()

        assert_that(confd.offsets('lines'), has_length(52))
        # 52 line pages and 1 trunk page at 1.5 s, 52 pauses of 200 ms
        assert_that(
            round(clock.now - start, 1), equal_to(round(53 * 1.5 + 52 * 0.2, 1))
        )
        assert_that(cache.status(), has_entries(build_seconds=89.9))

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

        assert_that(elapsed < 1.0, equal_to(True))
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

        at_request(confd, 'lines', 0, while_lines_load)

        assert_that(
            calling(cache.list_trunks).with_args('tenant'),
            raises(CalldUninitializedError),
        )
        assert_that(
            calling(cache.list_lines).with_args('tenant'),
            raises(CalldUninitializedError),
        )
        cache.build()

        assert_that(seen['trunks'], has_length(1))
        assert_that(seen['lines'].status_code, equal_to(503))
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


class TestObservability(TestCase):
    # criterion 12
    def test_status_walks_its_states_and_readiness(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(120)], [line(i) for i in range(50)]
        )
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
        confd.hooks.append(lambda kind, kwargs: snapshot())
        cache.start('token')
        cache._thread.join(5)
        snapshot()

        states = [s['confd_cache']['state'] for s in snapshots]
        assert_that(
            states,
            equal_to(
                [
                    'waiting_token',
                    'loading_trunks',
                    'loading_trunks',
                    'loading_lines',
                    'ready',
                ]
            ),
        )
        assert_that([s['status'] for s in snapshots], equal_to(['fail'] * 4 + ['ok']))
        assert_that(
            snapshots[2]['confd_cache'],
            has_entries(trunks_loaded=100, trunks_total=120, pages=1),
        )
        assert_that(
            snapshots[3]['confd_cache'],
            has_entries(trunks_loaded=120, lines_loaded=0, pages=2),
        )
        assert_that(
            snapshots[4]['confd_cache'],
            has_entries(
                lines_loaded=50,
                lines_total=50,
                pages=3,
                started_at='1970-01-12T13:46:40+00:00',
                ready_at='1970-01-12T13:46:40.400000+00:00',
                build_seconds=0.4,
            ),
        )

    # criterion 12
    def test_status_fails_while_ari_is_not_initialized(self):
        cache = new_cache(FakeConfd())
        cache.build()
        plugin = Plugin()
        plugin._confd_cache = cache
        plugin._async_tasks_completed = False
        status: StatusDict = {'plugins': {'endpoints': {}}}

        plugin._provide_status(status)

        assert_that(status['plugins']['endpoints']['status'], equal_to('fail'))

    # criterion 13
    def test_an_error_body_never_reaches_status_or_logs(self):
        confd = FakeConfd([], [line(1)])
        confd.errors = [http_error(500, 'secret-token-xyz')]
        cache = new_cache(confd)

        with self.assertLogs('wazo_calld.plugins.endpoints.services', 'DEBUG') as logs:
            cache.build()

        status = cache.status()
        assert_that(status, has_entries(last_error='HTTPError 500'))
        assert 'secret-token-xyz' not in str(status)
        assert 'secret-token-xyz' not in '\n'.join(logs.output)
        assert_that(status['last_error_at'], equal_to('1970-01-12T13:46:40+00:00'))

    # criterion 14
    def test_log_lines_are_key_value_and_end_with_the_totals(self):
        confd = FakeConfd(
            [sip_trunk(i) for i in range(3)], [line(i) for i in range(4600)]
        )
        confd.errors = [requests.ReadTimeout()]
        cache = new_cache(confd)

        with self.assertLogs('wazo_calld.plugins.endpoints.services', 'DEBUG') as logs:
            cache.build()

        messages = [record.getMessage() for record in logs.records]
        for message in messages:
            assert message.startswith('endpoint_cache '), message
            fields = message.split(' ')[1:]
            assert fields and all(
                '=' in field and field.split('=', 1)[0] for field in fields
            ), message
        last = dict(field.split('=', 1) for field in messages[-1].split(' ')[1:])
        assert_that(
            last,
            equal_to(
                {
                    'state': 'ready',
                    'lines': '4600',
                    'trunks': '3',
                    'seconds': '11.4',
                    'pages': '53',
                    'retries': '1',
                }
            ),
        )
        assert any('state=loading_lines' in m and 'pages=10' in m for m in messages)
        assert any(record.levelno == logging.WARNING for record in logs.records)

    # criterion 15
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


def test_status_before_any_token():
    cache = new_cache(FakeConfd())

    assert_that(
        cache.status(),
        has_entries(
            state='waiting_token',
            trunks_loaded=0,
            trunks_total=None,
            lines_loaded=0,
            lines_total=None,
            pages=0,
            skipped_items=0,
            retries=0,
            consecutive_failures=0,
            last_error=None,
            last_error_at=None,
            held_notifications=0,
            started_at=None,
            ready_at=None,
            build_seconds=None,
        ),
    )


class TestHeldAcrossBothIndexes(TestCase):
    # criterion 6: a line held before trunks are ready waits for the lines
    def test_a_line_held_before_trunks_are_ready_is_published_with_the_lines(self):
        confd = FakeConfd([sip_trunk(1)], [line(10, name='line-10')])
        cache, publisher, status_cache, handler = wire(confd)
        status_cache.add_endpoint(Endpoint('PJSIP', 'line-10', False, []))
        at_request(
            confd,
            'trunks',
            0,
            lambda: handler.on_new_channel(
                {'Channel': 'PJSIP/line-10-0001', 'Uniqueid': '1'}
            ),
        )
        held_while_lines_load = []
        at_request(
            confd,
            'lines',
            0,
            lambda: held_while_lines_load.append(cache.status()['held_notifications']),
        )

        cache.build()

        assert_that(held_while_lines_load, equal_to([1]))
        publisher.publish.assert_called_once_with(
            LineStatusUpdatedEvent(10, 'sip', 'line-10', False, 1, 'tenant')
        )


class TestTrunkIndex(TestCase):
    def test_trunks_are_found_by_id_name_and_registration_username(self):
        no_client_uri = sip_trunk(2)
        no_client_uri['endpoint_sip']['registration_section_options'] = []
        confd = FakeConfd([sip_trunk(1, name='t1', username='u1'), no_client_uri])
        cache = new_cache(confd)
        cache.build()

        assert_that(cache.get_trunk_by_id(1), has_entries(name='t1'))
        assert_that(cache.get_trunk_by_id(3), none())
        assert_that(cache.get_trunk('PJSIP', 'trunk-2'), has_entries(id=2))
        assert_that(cache.get_trunk_by_username('PJSIP', 'u1'), has_entries(id=1))
        assert_that(cache.get_trunk_by_username('PJSIP', None), none())


class TestPluginWiring(TestCase):
    # criteria 12 and 15: the build starts on a token, and /status reads it
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

        with patch('wazo_calld.plugins.endpoints.plugin.ConfdClient'):
            plugin.load(dependencies)  # type: ignore[arg-type]

        subscribed = [c.args[0] for c in token_changed_subscribe.call_args_list]
        assert_that(subscribed[-1], equal_to(plugin._confd_cache.start))
        assert_that(plugin._confd_cache._ready_callbacks, has_length(2))
        provider = status_aggregator.add_provider.call_args.args[0]
        status: StatusDict = {'plugins': {'endpoints': {}}}
        provider(status)
        assert_that(
            status['plugins']['endpoints'],
            has_entries(status='fail', confd_cache=has_entries(state='waiting_token')),
        )
