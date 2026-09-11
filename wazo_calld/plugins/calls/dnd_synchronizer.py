# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import re
import threading

from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.exceptions import WazoAmidError

logger = logging.getLogger(__name__)

USERS_PAGE_SIZE = 1000

GROUP_MEMBER_INTERFACE_RE = re.compile(r'^Local/(?P<user_uuid>[^@]+)@usersharedlines$')


def group_member_interface(user_uuid):
    return f'Local/{user_uuid}@usersharedlines'


class GroupDNDSynchronizer:
    '''Reconcile the pause state of group members with the DND state in confd.

    A user's DND is propagated to their groups by pausing their queue member,
    but that pause only lives in Asterisk's memory: group members are static
    members of queues.conf, so an Asterisk restart brings every member back
    unpaused. A wazo-calld restart is equally lossy, since DND events published
    while it was down are never seen.

    '''

    def __init__(self, amid_client, confd_client):
        self._amid = amid_client
        self._confd = confd_client
        self._lock = threading.Lock()
        self._synchronizing = False
        self._updated_while_synchronizing: set[str] = set()

    def pause_member(self, user_uuid):
        self._mark_updated(user_uuid)
        ami.pause_queue_member(self._amid, group_member_interface(user_uuid))

    def unpause_member(self, user_uuid):
        self._mark_updated(user_uuid)
        ami.unpause_queue_member(self._amid, group_member_interface(user_uuid))

    def _mark_updated(self, user_uuid):
        '''Record a DND event applied while a synchronization is in flight.

        Such an event carries a state newer than the snapshots the
        synchronization is working from, so the synchronization must not
        overwrite it with what confd reported before the change.

        '''
        with self._lock:
            if self._synchronizing:
                self._updated_while_synchronizing.add(user_uuid)

    def _updated_since_snapshot(self, user_uuid):
        with self._lock:
            return user_uuid in self._updated_while_synchronizing

    def synchronize(self):
        with self._lock:
            if self._synchronizing:
                logger.debug('DND synchronization already running, skipping')
                return
            self._synchronizing = True
            self._updated_while_synchronizing = set()

        try:
            self._synchronize()
        finally:
            with self._lock:
                self._synchronizing = False

    def _synchronize(self):
        dnd_by_user_uuid = self._fetch_dnd_states()
        pause_states_by_user_uuid = self._fetch_member_pause_states()

        corrected = 0
        skipped = 0
        failed = 0
        for user_uuid, pause_states in pause_states_by_user_uuid.items():
            enabled = dnd_by_user_uuid.get(user_uuid, False)
            if pause_states == {enabled}:
                continue

            if self._updated_since_snapshot(user_uuid):
                logger.debug(
                    'Skipping user "%s": DND was updated during synchronization',
                    user_uuid,
                )
                skipped += 1
                continue

            logger.debug(
                'Correcting pause state of user "%s" to "%s"', user_uuid, enabled
            )
            try:
                self._correct_pause_state(user_uuid, enabled)
            except WazoAmidError as e:
                logger.warning(
                    'Failed to correct pause state of user "%s": %s',
                    user_uuid,
                    e.details['original_error'],
                )
                failed += 1
                continue
            corrected += 1

        logger.info(
            'DND synchronization completed: %s group members inspected, '
            '%s corrected, %s skipped, %s failed',
            len(pause_states_by_user_uuid),
            corrected,
            skipped,
            failed,
        )

    def _correct_pause_state(self, user_uuid, enabled):
        if enabled:
            ami.pause_queue_member(self._amid, group_member_interface(user_uuid))
        else:
            ami.unpause_queue_member(self._amid, group_member_interface(user_uuid))

    def _fetch_dnd_states(self):
        result = self._confd.users.list(
            recurse=True,
            view='line_presence',
            limit=USERS_PAGE_SIZE,
            offset=0,
        )
        total = result['total']
        users = result['items']

        while len(users) < total:
            response = self._confd.users.list(
                recurse=True,
                view='line_presence',
                limit=USERS_PAGE_SIZE,
                offset=len(users),
            )
            new_users = response['items']
            if not new_users:
                logger.warning(
                    'No new users at offset %d while fetching DND states', len(users)
                )
                break
            users.extend(new_users)

        return {user['uuid']: user['services']['dnd']['enabled'] for user in users}

    def _fetch_member_pause_states(self):
        '''Map each group member to the pause states it has across its groups.

        A user belonging to several groups appears once per group, and those
        entries can disagree. The states are kept as a set rather than
        collapsed to a single value: a member paused in only some of its groups
        matches neither DND setting, and must be corrected in whichever
        direction confd dictates.

        '''
        pause_states_by_user_uuid: dict[str, set[bool]] = {}
        for event in ami.queue_status(self._amid):
            if event.get('Event') != 'QueueMember':
                continue

            match = GROUP_MEMBER_INTERFACE_RE.match(event.get('Location', ''))
            if not match:
                continue

            user_uuid = match.group('user_uuid')
            paused = event.get('Paused') == '1'
            pause_states_by_user_uuid.setdefault(user_uuid, set()).add(paused)

        return pause_states_by_user_uuid
