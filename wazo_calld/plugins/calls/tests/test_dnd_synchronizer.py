# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, call

from hamcrest import assert_that, calling, contains_inanyorder, empty, not_, raises
from requests import RequestException

from wazo_calld.plugin_helpers.exceptions import WazoAmidError

from ..dnd_synchronizer import GroupDNDSynchronizer

USER_1 = '11111111-1111-1111-1111-111111111111'
USER_2 = '22222222-2222-2222-2222-222222222222'


def queue_member(user_uuid, paused, queue='group1'):
    return {
        'Event': 'QueueMember',
        'Queue': queue,
        'Location': f'Local/{user_uuid}@usersharedlines',
        'Paused': '1' if paused else '0',
    }


class TestGroupDNDSynchronizer(TestCase):
    def setUp(self):
        self.amid = Mock()
        self.confd = Mock()
        self.synchronizer = GroupDNDSynchronizer(self.amid, self.confd)

    def _set_confd_users(self, *users):
        items = [
            {'uuid': uuid, 'services': {'dnd': {'enabled': enabled}}}
            for uuid, enabled in users
        ]
        self.confd.users.list.return_value = {'items': items, 'total': len(items)}

    def _set_queue_status(self, *events):
        self._queue_status_events = list(events)
        self.amid.action.return_value = self._queue_status_events + [
            {'Event': 'QueueStatusComplete'}
        ]

    def _queue_pause_actions(self):
        return [
            args[1]
            for args, _ in (c for c in self.amid.action.call_args_list)
            if args[0] == 'QueuePause'
        ]

    def test_unpaused_member_with_dnd_enabled_is_paused(self):
        self._set_confd_users((USER_1, True))
        self._set_queue_status(queue_member(USER_1, paused=False))

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True}
            ),
        )

    def test_paused_member_with_dnd_disabled_is_unpaused(self):
        self._set_confd_users((USER_1, False))
        self._set_queue_status(queue_member(USER_1, paused=True))

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': False}
            ),
        )

    def test_member_already_in_sync_is_left_alone(self):
        self._set_confd_users((USER_1, True), (USER_2, False))
        self._set_queue_status(
            queue_member(USER_1, paused=True),
            queue_member(USER_2, paused=False),
        )

        self.synchronizer.synchronize()

        assert_that(self._queue_pause_actions(), empty())

    def test_member_unknown_to_confd_is_unpaused(self):
        self._set_confd_users()
        self._set_queue_status(queue_member(USER_1, paused=True))

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': False}
            ),
        )

    def test_non_group_members_are_ignored(self):
        self._set_confd_users((USER_1, True))
        self._set_queue_status(
            {'Event': 'QueueMember', 'Location': 'Agent/1001', 'Paused': '0'},
            {'Event': 'QueueMember', 'Location': 'PJSIP/abc', 'Paused': '0'},
            {'Event': 'QueueParams', 'Queue': 'group1'},
        )

        self.synchronizer.synchronize()

        assert_that(self._queue_pause_actions(), empty())

    def test_user_in_several_groups_is_paused_once(self):
        self._set_confd_users((USER_1, True))
        self._set_queue_status(
            queue_member(USER_1, paused=False, queue='group1'),
            queue_member(USER_1, paused=False, queue='group2'),
            queue_member(USER_1, paused=False, queue='group3'),
        )

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True}
            ),
        )

    def test_user_paused_in_only_some_groups_is_paused_again(self):
        self._set_confd_users((USER_1, True))
        self._set_queue_status(
            queue_member(USER_1, paused=True, queue='group1'),
            queue_member(USER_1, paused=False, queue='group2'),
        )

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True}
            ),
        )

    def test_confd_paginates(self):
        page_1 = {
            'items': [{'uuid': USER_1, 'services': {'dnd': {'enabled': True}}}],
            'total': 2,
        }
        page_2 = {
            'items': [{'uuid': USER_2, 'services': {'dnd': {'enabled': True}}}],
            'total': 2,
        }
        self.confd.users.list.side_effect = [page_1, page_2]
        self._set_queue_status(
            queue_member(USER_1, paused=False),
            queue_member(USER_2, paused=False),
        )

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True},
                {'Interface': f'Local/{USER_2}@usersharedlines', 'Paused': True},
            ),
        )

    def test_confd_pagination_stops_on_empty_page(self):
        self.confd.users.list.side_effect = [
            {
                'items': [{'uuid': USER_1, 'services': {'dnd': {'enabled': True}}}],
                'total': 10,
            },
            {'items': [], 'total': 10},
        ]
        self._set_queue_status(queue_member(USER_1, paused=False))

        assert_that(calling(self.synchronizer.synchronize), not_(raises(Exception)))

    def test_amid_failure_is_raised_to_the_caller(self):
        self._set_confd_users((USER_1, True))
        self.amid.action.side_effect = RequestException()

        assert_that(calling(self.synchronizer.synchronize), raises(WazoAmidError))

    def test_lock_is_released_after_a_failure(self):
        self._set_confd_users((USER_1, True))
        self.amid.action.side_effect = RequestException()

        assert_that(calling(self.synchronizer.synchronize), raises(WazoAmidError))

        self.amid.action.side_effect = None
        self._set_queue_status(queue_member(USER_1, paused=False))
        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True}
            ),
        )

    def test_pause_member_uses_the_group_member_interface(self):
        self.synchronizer.pause_member(USER_1)

        assert_that(
            self.amid.action.call_args_list,
            contains_inanyorder(
                call(
                    'QueuePause',
                    {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True},
                )
            ),
        )

    def _handle_dnd_event_during_synchronization(self, user_uuid, enabled):
        '''Apply a DND event between the QueueStatus snapshot and the corrections.'''
        events = self._queue_status_events + [{'Event': 'QueueStatusComplete'}]
        handled: list[str] = []

        def action(name, body=None):
            if name != 'QueueStatus':
                return None
            if not handled:
                handled.append(name)
                if enabled:
                    self.synchronizer.pause_member(user_uuid)
                else:
                    self.synchronizer.unpause_member(user_uuid)
            return events

        self.amid.action.side_effect = action

    def test_dnd_enabled_during_synchronization_is_not_unpaused(self):
        self._set_confd_users((USER_1, False))
        self._set_queue_status(queue_member(USER_1, paused=True))
        self._handle_dnd_event_during_synchronization(USER_1, enabled=True)

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True}
            ),
        )

    def test_dnd_disabled_during_synchronization_is_not_paused(self):
        self._set_confd_users((USER_1, True))
        self._set_queue_status(queue_member(USER_1, paused=False))
        self._handle_dnd_event_during_synchronization(USER_1, enabled=False)

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': False}
            ),
        )

    def test_dnd_event_during_synchronization_spares_only_that_user(self):
        self._set_confd_users((USER_1, False), (USER_2, False))
        self._set_queue_status(
            queue_member(USER_1, paused=True),
            queue_member(USER_2, paused=True),
        )
        self._handle_dnd_event_during_synchronization(USER_1, enabled=True)

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': True},
                {'Interface': f'Local/{USER_2}@usersharedlines', 'Paused': False},
            ),
        )

    def test_dnd_event_outside_synchronization_is_not_remembered(self):
        self.synchronizer.pause_member(USER_1)
        self.amid.action.reset_mock()

        self._set_confd_users((USER_1, False))
        self._set_queue_status(queue_member(USER_1, paused=True))

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': False}
            ),
        )

    def test_a_later_synchronization_starts_from_a_clean_slate(self):
        self._set_confd_users((USER_1, False))
        self._set_queue_status(queue_member(USER_1, paused=True))
        self._handle_dnd_event_during_synchronization(USER_1, enabled=True)
        self.synchronizer.synchronize()

        self.amid.action.reset_mock()
        self.amid.action.side_effect = None
        self._set_queue_status(queue_member(USER_1, paused=True))

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': False}
            ),
        )

    def test_user_paused_in_only_some_groups_with_dnd_disabled_is_unpaused(self):
        self._set_confd_users((USER_1, False))
        self._set_queue_status(
            queue_member(USER_1, paused=True, queue='group1'),
            queue_member(USER_1, paused=False, queue='group2'),
        )

        self.synchronizer.synchronize()

        assert_that(
            self._queue_pause_actions(),
            contains_inanyorder(
                {'Interface': f'Local/{USER_1}@usersharedlines', 'Paused': False}
            ),
        )

    def test_user_paused_in_every_group_with_dnd_enabled_is_left_alone(self):
        self._set_confd_users((USER_1, True))
        self._set_queue_status(
            queue_member(USER_1, paused=True, queue='group1'),
            queue_member(USER_1, paused=True, queue='group2'),
        )

        self.synchronizer.synchronize()

        assert_that(self._queue_pause_actions(), empty())

    def test_user_unpaused_in_every_group_with_dnd_disabled_is_left_alone(self):
        self._set_confd_users((USER_1, False))
        self._set_queue_status(
            queue_member(USER_1, paused=False, queue='group1'),
            queue_member(USER_1, paused=False, queue='group2'),
        )

        self.synchronizer.synchronize()

        assert_that(self._queue_pause_actions(), empty())
