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
NOT_A_GROUP_MEMBER = 'Interface not found'

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
        self._synchronization_requested = False
        self._updated_while_synchronizing: dict[str, bool] = {}

    def pause_member(self, user_uuid):
        self._apply(user_uuid, True)

    def unpause_member(self, user_uuid):
        self._apply(user_uuid, False)

    def _apply(self, user_uuid, enabled):
        self._mark_updated(user_uuid, enabled)
        try:
            self._correct_pause_state(user_uuid, enabled)
        except Exception:
            self._unmark_updated(user_uuid)
            raise

    def _mark_updated(self, user_uuid, enabled):
        '''Record a DND event applied while a synchronization is in flight.

        Such an event carries a state newer than the snapshots the
        synchronization is working from, so the synchronization must not
        overwrite it with what confd reported before the change.

        '''
        with self._lock:
            if self._synchronizing:
                self._updated_while_synchronizing[user_uuid] = enabled

    def _unmark_updated(self, user_uuid):
        with self._lock:
            self._updated_while_synchronizing.pop(user_uuid, None)

    def _update_since_snapshot(self, user_uuid):
        with self._lock:
            return self._updated_while_synchronizing.get(user_uuid)

    def synchronize(self):
        with self._lock:
            if self._synchronizing:
                logger.debug(
                    'DND synchronization already running, scheduling another run'
                )
                self._synchronization_requested = True
                return
            self._synchronizing = True
            self._synchronization_requested = False
            self._updated_while_synchronizing = {}

        while True:
            try:
                self._synchronize()
            except Exception:
                if not self._another_run_requested():
                    raise
                logger.exception(
                    'DND synchronization failed, running the scheduled one anyway'
                )
                continue
            if not self._another_run_requested():
                return

    def _another_run_requested(self):
        with self._lock:
            if self._synchronization_requested:
                self._synchronization_requested = False
                self._updated_while_synchronizing = {}
                return True
            self._synchronizing = False
            return False

    def _synchronize(self):
        pause_states_by_user_uuid = self._fetch_member_pause_states()
        if not pause_states_by_user_uuid:
            logger.info('DND synchronization completed: no group member to inspect')
            return

        dnd_by_user_uuid = self._fetch_dnd_states()

        corrected = 0
        skipped = 0
        gone = 0
        for user_uuid, pause_states in pause_states_by_user_uuid.items():
            enabled = dnd_by_user_uuid.get(user_uuid, False)
            if pause_states == {enabled}:
                continue

            if self._update_since_snapshot(user_uuid) is not None:
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
                applied = enabled
                while True:
                    self._correct_pause_state(user_uuid, applied)
                    update = self._update_since_snapshot(user_uuid)
                    if update is None or update == applied:
                        break
                    logger.debug(
                        'DND of user "%s" was updated to "%s" while being corrected',
                        user_uuid,
                        update,
                    )
                    applied = update
            except WazoAmidError as e:
                if e.details['original_error'] != NOT_A_GROUP_MEMBER:
                    raise
                logger.warning(
                    'Member "%s" listed by QueueStatus but unknown to QueuePause, '
                    'skipping',
                    user_uuid,
                )
                gone += 1
                continue
            corrected += 1

        logger.info(
            'DND synchronization completed: %s group members inspected, '
            '%s corrected, %s skipped, %s gone',
            len(pause_states_by_user_uuid),
            corrected,
            skipped,
            gone,
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
