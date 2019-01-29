# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os

from ari.exceptions import ARINotFound
from hamcrest import (
    assert_that,
    calling,
    contains,
    contains_inanyorder,
    empty,
    equal_to,
    has_entries,
    has_entry,
    has_item,
    has_properties,
    is_,
)
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from xivo_ctid_ng_client.exceptions import CtidNGError
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import MockConference

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
CONFERENCE1_EXTENSION = '4001'
CONFERENCE1_ID = 4001


class TestConferences(RealAsteriskIntegrationTest):

    asset = 'real_asterisk_conference'

    def setUp(self):
        super().setUp()
        self.confd.reset()


class TestConferenceParticipants(TestConferences):

    def given_call_in_conference(self, conference_extension, caller_id_name=None):
        caller_id_name = caller_id_name or 'caller for {}'.format(conference_extension)
        channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='conferences',
            extension=CONFERENCE1_EXTENSION,
            variables={'variables': {'CALLERID(name)': caller_id_name}},
        )

        def channel_is_talking(channel):
            try:
                channel = self.ari.channels.get(channelId=channel.id)
            except ARINotFound:
                raise AssertionError('channel {} not found'.format(channel.id))
            assert_that(channel.json['state'], equal_to('Up'))

        until.assert_(channel_is_talking, channel, timeout=5)
        return channel.id

    def test_list_participants_with_no_confd(self):
        ctid_ng = self.make_ctid_ng()
        wrong_id = 14

        with self.confd_stopped():
            assert_that(calling(ctid_ng.conferences.list_participants).with_args(wrong_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))

    def test_list_participants_with_no_amid(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )

        with self.amid_stopped():
            assert_that(calling(ctid_ng.conferences.list_participants).with_args(conference_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-amid-error',
                        })))

    def test_list_participants_with_no_conferences(self):
        ctid_ng = self.make_ctid_ng()
        wrong_id = 14

        assert_that(calling(ctid_ng.conferences.list_participants).with_args(wrong_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                    })))

    def test_list_participants_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        ctid_ng = self.make_ctid_ng()

        participants = ctid_ng.conferences.list_participants(conference_id)

        assert_that(participants, has_entries({
            'total': 0,
            'items': empty(),
        }))

    def test_list_participants_with_two_participants(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant2')

        participants = ctid_ng.conferences.list_participants(conference_id)

        assert_that(participants, has_entries({
            'total': 2,
            'items': contains_inanyorder(
                has_entry('caller_id_name', 'participant1'),
                has_entry('caller_id_name', 'participant2'),
            )
        }))

    def test_participant_joins_sends_event(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        bus_events = self.bus.accumulator('conferences.{}.participants.joined'.format(conference_id))

        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        def participant_joined_event_received(expected_caller_id_name):
            caller_id_names = [event['data']['caller_id_name']
                               for event in bus_events.accumulate()]
            return expected_caller_id_name in caller_id_names

        until.true(participant_joined_event_received, 'participant1', tries=3)

    def test_participant_leaves_sends_event(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        bus_events = self.bus.accumulator('conferences.{}.participants.left'.format(conference_id))

        channel_id = self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        self.ari.channels.get(channelId=channel_id).hangup()

        def participant_left_event_received(expected_caller_id_name):
            caller_id_names = [event['data']['caller_id_name']
                               for event in bus_events.accumulate()]
            return expected_caller_id_name in caller_id_names

        until.true(participant_left_event_received, 'participant1', tries=3)

    def test_kick_participant_with_no_confd(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(calling(ctid_ng.conferences.kick_participant)
                        .with_args(conference_id, participant_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))

    def test_kick_participant_with_no_amid(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = ctid_ng.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(calling(ctid_ng.conferences.kick_participant)
                        .with_args(conference_id, participant['id']),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-amid-error',
                        })))

    def test_kick_participant_with_no_conferences(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = 14
        participant_id = '12345.67'

        assert_that(calling(ctid_ng.conferences.kick_participant)
                    .with_args(conference_id, participant_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))

    def test_kick_participant_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        participant_id = '12345.67'
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        ctid_ng = self.make_ctid_ng()

        assert_that(calling(ctid_ng.conferences.kick_participant)
                    .with_args(conference_id, participant_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))

    def test_kick_participant(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = ctid_ng.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        ctid_ng.conferences.kick_participant(conference_id, participant['id'])

        def no_more_participants():
            participants = ctid_ng.conferences.list_participants(conference_id)
            assert_that(participants, has_entries({
                'total': 0,
                'items': empty()
            }))
        until.assert_(no_more_participants, timeout=5, message='Participant was not kicked')

    def test_mute_participant_with_no_confd(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(calling(ctid_ng.conferences.mute_participant)
                        .with_args(conference_id, participant_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))
            assert_that(calling(ctid_ng.conferences.unmute_participant)
                        .with_args(conference_id, participant_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))

    def test_mute_participant_with_no_amid(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = ctid_ng.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(calling(ctid_ng.conferences.mute_participant)
                        .with_args(conference_id, participant['id']),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-amid-error',
                        })))
            assert_that(calling(ctid_ng.conferences.unmute_participant)
                        .with_args(conference_id, participant['id']),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-amid-error',
                        })))

    def test_mute_participant_with_no_conferences(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = 14
        participant_id = '12345.67'

        assert_that(calling(ctid_ng.conferences.mute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))
        assert_that(calling(ctid_ng.conferences.unmute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))

    def test_mute_participant_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        participant_id = '12345.67'
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        ctid_ng = self.make_ctid_ng()

        assert_that(calling(ctid_ng.conferences.mute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))
        assert_that(calling(ctid_ng.conferences.unmute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))

    def test_mute_unmute_participant(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = ctid_ng.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        ctid_ng.conferences.mute_participant(conference_id, participant['id'])

        def participant_is_muted():
            participants = ctid_ng.conferences.list_participants(conference_id)
            assert_that(participants, has_entries({
                'total': 1,
                'items': contains(has_entry('muted', True))
            }))
        until.assert_(participant_is_muted, timeout=5, message='Participant was not muted')

        ctid_ng.conferences.unmute_participant(conference_id, participant['id'])

        def participant_is_not_muted():
            participants = ctid_ng.conferences.list_participants(conference_id)
            assert_that(participants, has_entries({
                'total': 1,
                'items': contains(has_entry('muted', False))
            }))
        until.assert_(participant_is_not_muted, timeout=5, message='Participant is still muted')

    def test_mute_unmute_participant_twice(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = ctid_ng.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        ctid_ng.conferences.mute_participant(conference_id, participant['id'])
        ctid_ng.conferences.mute_participant(conference_id, participant['id'])

        # no error

        ctid_ng.conferences.unmute_participant(conference_id, participant['id'])
        ctid_ng.conferences.unmute_participant(conference_id, participant['id'])

        # no error

    def test_mute_unmute_participant_send_events(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = ctid_ng.conferences.list_participants(conference_id)
        participant = participants['items'][0]
        mute_bus_events = self.bus.accumulator('conferences.{}.participants.mute'.format(conference_id))

        ctid_ng.conferences.mute_participant(conference_id, participant['id'])

        def participant_muted_event_received(muted):
            assert_that(mute_bus_events.accumulate(), has_item(has_entries({
                'name': 'conference_participant_muted' if muted else 'conference_participant_unmuted',
                'data': has_entries({
                    'id': participant['id'],
                    'conference_id': conference_id,
                    'muted': muted,
                })
            })))

        until.assert_(participant_muted_event_received, muted=True, timeout=5, message='Mute event was not received')

        ctid_ng.conferences.unmute_participant(conference_id, participant['id'])

        until.assert_(participant_muted_event_received, muted=True, timeout=5, message='Unmute event was not received')

    def test_record_with_no_confd(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = 14

        with self.confd_stopped():
            assert_that(calling(ctid_ng.conferences.record)
                        .with_args(conference_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))
            assert_that(calling(ctid_ng.conferences.stop_record)
                        .with_args(conference_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))

    def test_record_with_no_amid(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        with self.amid_stopped():
            assert_that(calling(ctid_ng.conferences.record)
                        .with_args(conference_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-amid-error',
                        })))
            assert_that(calling(ctid_ng.conferences.stop_record)
                        .with_args(conference_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-amid-error',
                        })))

    def test_record_with_no_conferences(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = 14

        assert_that(calling(ctid_ng.conferences.record)
                    .with_args(conference_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))
        assert_that(calling(ctid_ng.conferences.stop_record)
                    .with_args(conference_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))

    def test_record_participant_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        ctid_ng = self.make_ctid_ng()

        assert_that(calling(ctid_ng.conferences.record)
                    .with_args(conference_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'conference-has-no-participants',
                    })))

    def test_record(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        def file_size(file_path):
            return int(self.docker_exec(['stat', '-c', '%s', file_path], 'ari').strip())

        def record_file_is_growing():
            record_files = self.docker_exec(['ls', '-t', '/var/spool/asterisk/monitor'], 'ari')
            record_file = record_files.split(b'\n')[0].decode('utf-8')
            record_file_size_1 = file_size(os.path.join('/var/spool/asterisk/monitor', record_file))
            record_file_size_2 = file_size(os.path.join('/var/spool/asterisk/monitor', record_file))
            return record_file_size_1 < record_file_size_2

        ctid_ng.conferences.record(conference_id)
        assert_that(record_file_is_growing(), is_(True))

        ctid_ng.conferences.stop_record(conference_id)
        assert_that(record_file_is_growing(), is_(False))

    def test_record_twice(self):
        ctid_ng = self.make_ctid_ng()
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        # record twice
        ctid_ng.conferences.record(conference_id)
        assert_that(calling(ctid_ng.conferences.record)
                    .with_args(conference_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'conference-already-recorded',
                    })))

        # stop record twice
        ctid_ng.conferences.stop_record(conference_id)
        assert_that(calling(ctid_ng.conferences.stop_record)
                    .with_args(conference_id),
                    raises(CtidNGError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'conference-not-recorded',
                    })))
