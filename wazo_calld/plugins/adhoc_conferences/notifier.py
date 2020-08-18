# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.adhoc_conference.event import (
    AdhocConferenceCreatedUserEvent,
    AdhocConferenceDeletedUserEvent,
)


class AdhocConferencesNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def created(self, adhoc_conference_id, host_user_uuid):
        headers = {
            f'user_uuid:{host_user_uuid}': True
        }
        event = AdhocConferenceCreatedUserEvent(adhoc_conference_id, host_user_uuid)
        self._bus_producer.publish(event, headers=headers)

    def deleted(self, adhoc_conference_id, host_user_uuid):
        headers = {
            f'user_uuid:{host_user_uuid}': True
        }
        event = AdhocConferenceDeletedUserEvent(adhoc_conference_id, host_user_uuid)
        self._bus_producer.publish(event, headers=headers)
