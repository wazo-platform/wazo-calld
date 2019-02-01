# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from .schemas import participant_schema

logger = logging.getLogger(__name__)


class ConferencesBusEventHandler:

    def __init__(self, notifier):
        self._notifier = notifier

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('ConfbridgeJoin', self._notify_participant_joined)
        bus_consumer.on_ami_event('ConfbridgeLeave', self._notify_participant_left)
        bus_consumer.on_ami_event('ConfbridgeMute', self._notify_participant_muted)
        bus_consumer.on_ami_event('ConfbridgeUnmute', self._notify_participant_unmuted)
        bus_consumer.on_ami_event('ConfbridgeRecord', self._notify_record_started)
        bus_consumer.on_ami_event('ConfbridgeStopRecord', self._notify_record_stopped)

    def _notify_participant_joined(self, event):
        conference_id = int(event['Conference'])
        logger.debug('Participant joined conference %s', conference_id)
        raw_participant = {
            'id': event['Uniqueid'],
            'caller_id_name': event['CallerIDName'],
            'caller_id_number': event['CallerIDNum'],
            'muted': event['Muted'] == 'Yes',
            'answered_time': 0,
            'admin': event['Admin'] == 'Yes',
            'language': event['Language'],
            'call_id': event['Uniqueid'],
        }

        participant = participant_schema.load(raw_participant).data

        self._notifier.participant_joined(conference_id, participant)

    def _notify_participant_left(self, event):
        conference_id = int(event['Conference'])
        logger.debug('Participant left conference %s', conference_id)
        raw_participant = {
            'id': event['Uniqueid'],
            'caller_id_name': event['CallerIDName'],
            'caller_id_number': event['CallerIDNum'],
            'muted': False,
            'answered_time': '0',
            'admin': event['Admin'] == 'Yes',
            'language': event['Language'],
            'call_id': event['Uniqueid'],
        }

        participant = participant_schema.load(raw_participant).data

        self._notifier.participant_left(conference_id, participant)

    def _notify_participant_muted(self, event):
        conference_id = int(event['Conference'])
        logger.debug('Participant in conference %s was muted', conference_id)
        raw_participant = {
            'id': event['Uniqueid'],
            'caller_id_name': event['CallerIDName'],
            'caller_id_number': event['CallerIDNum'],
            'muted': True,
            'answered_time': '0',
            'admin': event['Admin'] == 'Yes',
            'language': event['Language'],
            'call_id': event['Uniqueid'],
        }

        participant = participant_schema.load(raw_participant).data

        self._notifier.participant_muted(conference_id, participant)

    def _notify_participant_unmuted(self, event):
        conference_id = int(event['Conference'])
        logger.debug('Participant in conference %s was unmuted', conference_id)
        raw_participant = {
            'id': event['Uniqueid'],
            'caller_id_name': event['CallerIDName'],
            'caller_id_number': event['CallerIDNum'],
            'muted': False,
            'answered_time': '0',
            'admin': event['Admin'] == 'Yes',
            'language': event['Language'],
            'call_id': event['Uniqueid'],
        }

        participant = participant_schema.load(raw_participant).data

        self._notifier.participant_unmuted(conference_id, participant)

    def _notify_record_started(self, event):
        conference_id = int(event['Conference'])
        logger.debug('Conference %s is being recorded', conference_id)

        self._notifier.conference_record_started(conference_id)

    def _notify_record_stopped(self, event):
        conference_id = int(event['Conference'])
        logger.debug('Conference %s is not being recorded', conference_id)

        self._notifier.conference_record_stopped(conference_id)
