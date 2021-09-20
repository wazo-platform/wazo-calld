# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import unittest
import uuid

from hamcrest import (
    assert_that,
    calling,
    contains,
    contains_inanyorder,
    empty,
    has_entries,
    has_entry,
    has_item,
    has_items,
    has_properties,
    is_,
    less_than,
)
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError
from .helpers.confd import MockMeeting
from .helpers.constants import ENDPOINT_AUTOANSWER
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsteriskIntegrationTest

MEETING1_EXTENSION = 'meeting-user'
MEETING1_UUID = '6267d321-1d42-41ac-be3d-551a318c745b'
MEETING1_TENANT_UUID = '404afda0-36ba-43de-9571-a06c81b9c43e'


def make_user_uuid():
    return str(uuid.uuid4())


class TestMeetings(RealAsteriskIntegrationTest):

    asset = 'real_asterisk_conference'

    def setUp(self):
        super().setUp()
        self.confd.reset()


class TestMeetingParticipants(TestMeetings):

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)

    def given_call_in_meeting(self, meeting_extension, caller_id_name=None, user_uuid=None):
        caller_id_name = caller_id_name or 'caller for {}'.format(meeting_extension)
        variables = {'CALLERID(name)': caller_id_name}
        if user_uuid:
            variables['XIVO_USERUUID'] = user_uuid
        channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='meetings',
            extension=MEETING1_EXTENSION,
            variables={'variables': variables},
        )

        def channel_is_in_meeting(channel):
            assert_that(channel.id, self.c.is_in_bridge(), 'Channel is not in meeting')

        until.assert_(channel_is_in_meeting, channel, timeout=10)
        return channel.id

    def test_list_participants_with_no_confd(self):
        wrong_id = 14

        with self.confd_stopped():
            assert_that(calling(self.calld_client.meetings.list_participants).with_args(wrong_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    def test_list_participants_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        with self.amid_stopped():
            assert_that(calling(self.calld_client.meetings.list_participants).with_args(meeting_uuid),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    def test_list_participants_with_no_meetings(self):
        wrong_id = 14

        assert_that(calling(self.calld_client.meetings.list_participants).with_args(wrong_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                    })))

    def test_list_participants_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        participants = self.calld_client.meetings.list_participants(meeting_uuid)

        assert_that(participants, has_entries({
            'total': 0,
            'items': empty(),
        }))

    def test_user_list_participants_when_user_is_not_participant(self):
        user_uuid = 'user-uuid'
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        calld_client = self.make_user_calld(user_uuid)

        assert_that(calling(calld_client.meetings.user_list_participants).with_args(meeting_uuid),
                    raises(CalldError).matching(has_properties({
                        'status_code': 403,
                        'error_id': 'user-not-participant',
                    })))

    def test_user_list_participants_when_user_is_participant(self):
        user_uuid = 'user-uuid'
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1', user_uuid=user_uuid)
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')
        calld_client = self.make_user_calld(user_uuid)

        participants = calld_client.meetings.user_list_participants(meeting_uuid)

        assert_that(participants, has_entries({
            'total': 2,
            'items': contains_inanyorder(
                has_entry('caller_id_name', 'participant1'),
                has_entry('caller_id_name', 'participant2'),
            )
        }))

    def test_list_participants_with_two_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')

        participants = self.calld_client.meetings.list_participants(meeting_uuid)

        assert_that(participants, has_entries({
            'total': 2,
            'items': contains_inanyorder(
                has_entry('caller_id_name', 'participant1'),
                has_entry('caller_id_name', 'participant2'),
            )
        }))

    def test_participant_joins_sends_event(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        bus_events = self.bus.accumulator(f'meetings.{meeting_uuid}.participants.joined')

        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        def participant_joined_event_received(expected_caller_id_name):
            caller_id_names = [event['data']['caller_id_name']
                               for event in bus_events.accumulate()]
            return expected_caller_id_name in caller_id_names

        until.true(participant_joined_event_received, 'participant1', timeout=10)

    def test_user_participant_joins_sends_event(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        meeting_bus_events = self.bus.accumulator(f'meetings.users.{user_uuid}.participants.joined')
        call_bus_events = self.bus.accumulator('calls.call.updated')

        self.given_call_in_meeting(MEETING1_EXTENSION, user_uuid=user_uuid)
        other_channel_id = self.given_call_in_meeting(MEETING1_EXTENSION, user_uuid=other_user_uuid)

        def user_participant_joined_event_received(first_user_uuid, second_user_uuid):
            assert_that(
                meeting_bus_events.accumulate(),
                has_items(
                    has_entries({
                        'name': 'meeting_user_participant_joined',
                        'data': has_entries({
                            'user_uuid': first_user_uuid,
                        })
                    }),
                    has_entries({
                        'name': 'meeting_user_participant_joined',
                        'data': has_entries({
                            'user_uuid': second_user_uuid,
                        })
                    })
                )
            )
            assert_that(
                call_bus_events.accumulate(),
                has_items(
                    has_entries({
                        'name': 'call_updated',
                        'data': has_entries({
                            'user_uuid': first_user_uuid,
                            'talking_to': has_entries({
                                other_channel_id: second_user_uuid
                            })
                        })
                    }),
                )
            )

        until.assert_(user_participant_joined_event_received, user_uuid, other_user_uuid, timeout=10)

    def test_participant_leaves_sends_event(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        bus_events = self.bus.accumulator(f'meetings.{meeting_uuid}.participants.left')

        channel_id = self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        self.ari.channels.hangup(channelId=channel_id)

        def participant_left_event_received(expected_caller_id_name):
            caller_id_names = [event['data']['caller_id_name']
                               for event in bus_events.accumulate()]
            return expected_caller_id_name in caller_id_names

        until.true(participant_left_event_received, 'participant1', timeout=10)

    def test_user_participant_leaves_sends_event(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        meeting_bus_events = self.bus.accumulator(f'meetings.users.{user_uuid}.participants.left')
        call_bus_events = self.bus.accumulator('calls.call.updated')

        channel_id = self.given_call_in_meeting(MEETING1_EXTENSION, user_uuid=user_uuid)
        other_channel_id = self.given_call_in_meeting(MEETING1_EXTENSION, user_uuid=other_user_uuid)

        def user_participant_left_event_received(expected_user_uuid):
            assert_that(
                meeting_bus_events.accumulate(),
                has_items(
                    has_entries({
                        'name': 'meeting_user_participant_left',
                        'data': has_entries({
                            'user_uuid': expected_user_uuid,
                        })
                    }),
                )
            )

        def call_updated_event_received():
            assert_that(
                call_bus_events.accumulate(),
                has_items(
                    has_entries({
                        'name': 'call_updated',
                        'data': has_entries({
                            'user_uuid': user_uuid,
                            'talking_to': empty(),
                        })
                    }),
                )
            )

        self.ari.channels.hangup(channelId=other_channel_id)

        until.assert_(user_participant_left_event_received, other_user_uuid, timeout=10)
        until.assert_(call_updated_event_received, timeout=10)

        self.ari.channels.hangup(channelId=channel_id)

        until.assert_(user_participant_left_event_received, user_uuid, timeout=10)

    @unittest.skip
    def test_kick_participant_with_no_confd(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(calling(self.calld_client.meetings.kick_participant)
                        .with_args(meeting_uuid, participant_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    @unittest.skip
    def test_kick_participant_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(calling(self.calld_client.meetings.kick_participant)
                        .with_args(meeting_uuid, participant['id']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    @unittest.skip
    def test_kick_participant_with_no_meetings(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        assert_that(calling(self.calld_client.meetings.kick_participant)
                    .with_args(meeting_uuid, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    })))

    @unittest.skip
    def test_kick_participant_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        participant_id = '12345.67'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        assert_that(calling(self.calld_client.meetings.kick_participant)
                    .with_args(meeting_uuid, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))

    @unittest.skip
    def test_kick_participant(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        self.calld_client.meetings.kick_participant(meeting_uuid, participant['id'])

        def no_more_participants():
            participants = self.calld_client.meetings.list_participants(meeting_uuid)
            assert_that(participants, has_entries({
                'total': 0,
                'items': empty()
            }))
        until.assert_(no_more_participants, timeout=10, message='Participant was not kicked')

    @unittest.skip
    def test_mute_participant_with_no_confd(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(calling(self.calld_client.meetings.mute_participant)
                        .with_args(meeting_uuid, participant_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))
            assert_that(calling(self.calld_client.meetings.unmute_participant)
                        .with_args(meeting_uuid, participant_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    @unittest.skip
    def test_mute_participant_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(calling(self.calld_client.meetings.mute_participant)
                        .with_args(meeting_uuid, participant['id']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))
            assert_that(calling(self.calld_client.meetings.unmute_participant)
                        .with_args(meeting_uuid, participant['id']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    @unittest.skip
    def test_mute_participant_with_no_meetings(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        assert_that(calling(self.calld_client.meetings.mute_participant)
                    .with_args(meeting_uuid, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    })))
        assert_that(calling(self.calld_client.meetings.unmute_participant)
                    .with_args(meeting_uuid, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    })))

    @unittest.skip
    def test_mute_participant_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        participant_id = '12345.67'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        assert_that(calling(self.calld_client.meetings.mute_participant)
                    .with_args(meeting_uuid, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))
        assert_that(calling(self.calld_client.meetings.unmute_participant)
                    .with_args(meeting_uuid, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))

    @unittest.skip
    def test_mute_unmute_participant(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        self.calld_client.meetings.mute_participant(meeting_uuid, participant['id'])

        def participant_is_muted():
            participants = self.calld_client.meetings.list_participants(meeting_uuid)
            assert_that(participants, has_entries({
                'total': 1,
                'items': contains(has_entry('muted', True))
            }))
        until.assert_(participant_is_muted, timeout=10, message='Participant was not muted')

        self.calld_client.meetings.unmute_participant(meeting_uuid, participant['id'])

        def participant_is_not_muted():
            participants = self.calld_client.meetings.list_participants(meeting_uuid)
            assert_that(participants, has_entries({
                'total': 1,
                'items': contains(has_entry('muted', False))
            }))
        until.assert_(participant_is_not_muted, timeout=10, message='Participant is still muted')

    @unittest.skip
    def test_mute_unmute_participant_twice(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        self.calld_client.meetings.mute_participant(meeting_uuid, participant['id'])
        self.calld_client.meetings.mute_participant(meeting_uuid, participant['id'])

        # no error

        self.calld_client.meetings.unmute_participant(meeting_uuid, participant['id'])
        self.calld_client.meetings.unmute_participant(meeting_uuid, participant['id'])

        # no error

    @unittest.skip
    def test_mute_unmute_participant_send_events(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]
        mute_bus_events = self.bus.accumulator('meetings.{}.participants.mute'.format(meeting_uuid))

        self.calld_client.meetings.mute_participant(meeting_uuid, participant['id'])

        def participant_muted_event_received(muted):
            assert_that(mute_bus_events.accumulate(), has_item(has_entries({
                'name': 'meeting_participant_muted' if muted else 'meeting_participant_unmuted',
                'data': has_entries({
                    'id': participant['id'],
                    'meeting_uuid': meeting_uuid,
                    'muted': muted,
                })
            })))

        until.assert_(participant_muted_event_received, muted=True, timeout=10, message='Mute event was not received')

        self.calld_client.meetings.unmute_participant(meeting_uuid, participant['id'])

        until.assert_(participant_muted_event_received, muted=True, timeout=10, message='Unmute event was not received')

    @unittest.skip
    def test_record_with_no_confd(self):
        meeting_uuid = 14

        with self.confd_stopped():
            assert_that(calling(self.calld_client.meetings.record)
                        .with_args(meeting_uuid),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))
            assert_that(calling(self.calld_client.meetings.stop_record)
                        .with_args(meeting_uuid),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    @unittest.skip
    def test_record_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        with self.amid_stopped():
            assert_that(calling(self.calld_client.meetings.record)
                        .with_args(meeting_uuid),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))
            assert_that(calling(self.calld_client.meetings.stop_record)
                        .with_args(meeting_uuid),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    @unittest.skip
    def test_record_with_no_meetings(self):
        meeting_uuid = 14

        assert_that(calling(self.calld_client.meetings.record)
                    .with_args(meeting_uuid),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    })))
        assert_that(calling(self.calld_client.meetings.stop_record)
                    .with_args(meeting_uuid),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    })))

    @unittest.skip
    def test_record_participant_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        assert_that(calling(self.calld_client.meetings.record)
                    .with_args(meeting_uuid),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'meeting-has-no-participants',
                    })))

    @unittest.skip
    def test_record(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        def latest_record_file():
            record_files = self.docker_exec(['ls', '-t', '/var/spool/asterisk/monitor'], 'ari')
            latest_record_file = record_files.split(b'\n')[0].decode('utf-8')
            return os.path.join('/var/spool/asterisk/monitor', latest_record_file)

        def file_size(file_path):
            return int(self.docker_exec(['stat', '-c', '%s', file_path], 'ari').strip())

        self.calld_client.meetings.record(meeting_uuid)
        record_file = latest_record_file()
        record_file_size_1 = file_size(record_file)

        def record_file_is_growing():
            record_file_size_2 = file_size(record_file)
            assert_that(record_file_size_1, less_than(record_file_size_2))

        until.assert_(record_file_is_growing, timeout=10, message='file did not grow')

        def record_file_is_closed():
            record_file = latest_record_file()
            writing_pids = self.docker_exec(['fuser', record_file], 'ari').strip()
            return writing_pids == b''

        self.calld_client.meetings.stop_record(meeting_uuid)
        assert_that(record_file_is_closed(), is_(True))

    @unittest.skip
    def test_record_twice(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        # record twice
        self.calld_client.meetings.record(meeting_uuid)
        assert_that(calling(self.calld_client.meetings.record)
                    .with_args(meeting_uuid),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'meeting-already-recorded',
                    })))

        # stop record twice
        self.calld_client.meetings.stop_record(meeting_uuid)
        assert_that(calling(self.calld_client.meetings.stop_record)
                    .with_args(meeting_uuid),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'meeting-not-recorded',
                    })))

    @unittest.skip
    def test_record_send_events(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        record_bus_events = self.bus.accumulator('meetings.{}.record'.format(meeting_uuid))

        self.calld_client.meetings.record(meeting_uuid)

        def record_event_received(record):
            assert_that(record_bus_events.accumulate(), has_item(has_entries({
                'name': 'meeting_record_started' if record else 'meeting_record_stopped',
                'data': has_entries({
                    'id': meeting_uuid,
                })
            })))

        until.assert_(record_event_received, record=True, timeout=10, message='Record start event was not received')

        self.calld_client.meetings.stop_record(meeting_uuid)

        until.assert_(record_event_received, record=False, timeout=10, message='Record stop event was not received')

    @unittest.skip
    def test_participant_talking_sends_event(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        talking_user_uuid = 'talking-user-uuid'
        listening_user_uuid = 'listening-user-uuid'

        admin_bus_events = self.bus.accumulator(f'meetings.{meeting_uuid}.participants.talk')
        talking_user_bus_events = self.bus.accumulator(f'meetings.users.{talking_user_uuid}.participants.talk')
        listening_user_bus_events = self.bus.accumulator(f'meetings.users.{listening_user_uuid}.participants.talk')

        # listening user must enter the meeting first, to receive the event from the talking user
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2', user_uuid=listening_user_uuid)
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1', user_uuid=talking_user_uuid)
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        talking_participant = [participant for participant in participants['items'] if participant['user_uuid'] == talking_user_uuid][0]

        def talking_event_received(bus_events, talking):
            assert_that(bus_events.accumulate(), has_item(has_entries({
                'name': 'meeting_participant_talk_started' if talking else 'meeting_participant_talk_stopped',
                'data': has_entries({
                    'id': talking_participant['id'],
                    'meeting_uuid': meeting_uuid,
                })
            })))

        def talking_user_event_received(bus_events, talking):
            assert_that(bus_events.accumulate(), has_item(has_entries({
                'name': 'meeting_user_participant_talk_started' if talking else 'meeting_user_participant_talk_stopped',
                'data': has_entries({
                    'id': talking_participant['id'],
                    'meeting_uuid': meeting_uuid,
                })
            })))

        until.assert_(talking_event_received, admin_bus_events, talking=True, timeout=10)
        until.assert_(talking_user_event_received, talking_user_bus_events, talking=True, timeout=10)
        until.assert_(talking_user_event_received, listening_user_bus_events, talking=True, timeout=10)

        # send fake "stopped talking" AMI event
        self.bus.publish(
            {
                'name': 'ConfbridgeTalking',
                'data': {
                    'Event': 'ConfbridgeTalking',
                    'Conference': f'wazo-meeting-{meeting_uuid}-confbridge',
                    'CallerIDNum': talking_participant['caller_id_number'],
                    'CallerIDName': talking_participant['caller_id_name'],
                    'Admin': 'No',
                    'Language': talking_participant['language'],
                    'Uniqueid': talking_participant['id'],
                    'TalkingStatus': 'off',
                }
            },
            routing_key='ami.ConfbridgeTalking'
        )

        until.assert_(talking_event_received, admin_bus_events, talking=False, timeout=10)
        until.assert_(talking_user_event_received, talking_user_bus_events, talking=False)
        until.assert_(talking_user_event_received, listening_user_bus_events, talking=False)