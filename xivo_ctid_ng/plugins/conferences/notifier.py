# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.conference.event import (
    ParticipantJoinedConferenceEvent,
    ParticipantLeftConferenceEvent,
    ParticipantMutedConferenceEvent,
    ParticipantTalkStartedConferenceEvent,
    ParticipantTalkStoppedConferenceEvent,
    ParticipantUnmutedConferenceEvent,
    RecordStartedConferenceEvent,
    RecordStoppedConferenceEvent,
)


class ConferencesNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def participant_joined(self, conference_id, participant):
        event = ParticipantJoinedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def participant_left(self, conference_id, participant):
        event = ParticipantLeftConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def participant_muted(self, conference_id, participant):
        event = ParticipantMutedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def participant_unmuted(self, conference_id, participant):
        event = ParticipantUnmutedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def conference_record_started(self, conference_id):
        event = RecordStartedConferenceEvent(conference_id)
        self._bus_producer.publish(event)

    def conference_record_stopped(self, conference_id):
        event = RecordStoppedConferenceEvent(conference_id)
        self._bus_producer.publish(event)

    def participant_talk_started(self, conference_id, participant):
        event = ParticipantTalkStartedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def participant_talk_stopped(self, conference_id, participant):
        event = ParticipantTalkStoppedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)
