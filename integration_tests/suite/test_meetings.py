# Copyright 2021-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import unittest
import uuid

from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    contains_inanyorder,
    empty,
    has_entries,
    has_entry,
    has_item,
    has_items,
    has_properties,
    is_,
    is_not,
    less_than,
)
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError
from .helpers.confd import MockMeeting
from .helpers.constants import ENDPOINT_AUTOANSWER
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsteriskIntegrationTest

MEETING1_EXTENSION = 'meeting1-user'
MEETING1_UUID = '6267d321-1d42-41ac-be3d-551a318c745b'
MEETING1_TENANT_UUID = '404afda0-36ba-43de-9571-a06c81b9c43e'

MEETING2_EXTENSION = 'meeting2-user'
MEETING2_UUID = '9ae6eb46-489b-42fc-8184-6a9a2bf6c48a'
MEETING2_TENANT_UUID = '404afda0-36ba-43de-9571-a06c81b9c43e'

EMPTY_MEETING_UUID = '1e366c30-4708-4bd3-a386-b27b4a237c22'
EMPTY_MEETING_TENANT_UUID = '404afda0-36ba-43de-9571-a06c81b9c43e'


def make_user_uuid():
    return str(uuid.uuid4())


class TestMeetings(RealAsteriskIntegrationTest):
    asset = 'real_asterisk_conference'

    def setUp(self):
        super().setUp()
        self.confd.reset()
        self.c = HamcrestARIChannel(self.ari)

    def given_call_in_meeting(
        self, meeting_extension, caller_id_name=None, user_uuid=None, tenant_uuid=None
    ):
        caller_id_name = caller_id_name or f'caller for {meeting_extension}'
        variables = {'CALLERID(name)': caller_id_name}
        if user_uuid:
            variables['WAZO_USERUUID'] = user_uuid
        if tenant_uuid:
            variables['WAZO_TENANT_UUID'] = tenant_uuid
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


class TestMeetingStatus(TestMeetings):
    def test_get_no_confd(self):
        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.meetings.guest_status).with_args(
                    MEETING1_UUID
                ),
                raises(CalldError).matching(
                    has_properties(
                        status_code=503,
                        error_id='wazo-confd-unreachable',
                    )
                ),
            )

    def test_get_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        with self.amid_stopped():
            assert_that(
                calling(self.calld_client.meetings.guest_status).with_args(
                    meeting_uuid
                ),
                raises(CalldError).matching(
                    has_properties(
                        status_code=503,
                        error_id='wazo-amid-error',
                    )
                ),
            )

    def test_get_no_meetings(self):
        wrong_id = '00000000-0000-0000-0000-000000000000'

        assert_that(
            calling(self.calld_client.meetings.guest_status).with_args(wrong_id),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_get_with_some_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')

        status = self.calld_client.meetings.guest_status(meeting_uuid)

        assert_that(status, has_entries(full=False))

    def test_get_with_max_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        # The max number of participants is in the overloaded configuration file
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant3')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant4')

        status = self.calld_client.meetings.guest_status(meeting_uuid)

        assert_that(status, has_entries(full=True))

    def test_get_with_no_participant(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        status = self.calld_client.meetings.guest_status(meeting_uuid)

        assert_that(status, has_entries(full=False))

    def test_get_with_participants_in_other_meeting(self):
        meeting_uuid = 'a58471f5-3d4d-4b85-b6bd-a388fef42a0e'
        other_meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
            MockMeeting(uuid=other_meeting_uuid, name='other meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant3')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant4')

        status = self.calld_client.meetings.guest_status(meeting_uuid)

        assert_that(status, has_entries(full=False))


class TestMeetingParticipants(TestMeetings):
    def test_list_participants_with_no_confd(self):
        wrong_id = 14

        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.meetings.list_participants).with_args(
                    wrong_id
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        }
                    )
                ),
            )

    def test_list_participants_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        with self.amid_stopped():
            assert_that(
                calling(self.calld_client.meetings.list_participants).with_args(
                    meeting_uuid
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )

    def test_list_participants_with_no_meetings(self):
        wrong_id = 14

        assert_that(
            calling(self.calld_client.meetings.list_participants).with_args(wrong_id),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                    }
                )
            ),
        )

    def test_list_participants_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        participants = self.calld_client.meetings.list_participants(meeting_uuid)

        assert_that(
            participants,
            has_entries(
                {
                    'total': 0,
                    'items': empty(),
                }
            ),
        )

    def test_list_participants_with_participants_on_other_only(self):
        meeting_uuid = 'a58471f5-3d4d-4b85-b6bd-a388fef42a0e'
        other_meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
            MockMeeting(uuid=other_meeting_uuid, name='other meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        participants = self.calld_client.meetings.list_participants(meeting_uuid)

        assert_that(
            participants,
            has_entries(
                {
                    'total': 0,
                    'items': empty(),
                }
            ),
        )

    def test_user_list_participants_when_user_is_not_participant(self):
        user_uuid = 'user-uuid'
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        calld_client = self.make_user_calld(user_uuid)

        assert_that(
            calling(calld_client.meetings.user_list_participants).with_args(
                meeting_uuid
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 403,
                        'error_id': 'user-not-participant',
                    }
                )
            ),
        )

    def test_user_list_participants_when_user_is_participant(self):
        user_uuid = 'user-uuid'
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(
            MEETING1_EXTENSION, caller_id_name='participant1', user_uuid=user_uuid
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')
        calld_client = self.make_user_calld(user_uuid)

        participants = calld_client.meetings.user_list_participants(meeting_uuid)

        assert_that(
            participants,
            has_entries(
                {
                    'total': 2,
                    'items': contains_inanyorder(
                        has_entry('caller_id_name', 'participant1'),
                        has_entry('caller_id_name', 'participant2'),
                    ),
                }
            ),
        )

    def test_list_participants_with_two_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant2')

        participants = self.calld_client.meetings.list_participants(meeting_uuid)

        assert_that(
            participants,
            has_entries(
                {
                    'total': 2,
                    'items': contains_inanyorder(
                        has_entry('caller_id_name', 'participant1'),
                        has_entry('caller_id_name', 'participant2'),
                    ),
                }
            ),
        )

    def test_participant_joins_sends_event(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        self.confd.set_meetings(
            MockMeeting(
                uuid=meeting_uuid,
                tenant_uuid=tenant_uuid,
                name='meeting',
            ),
        )
        bus_events = self.bus.accumulator(headers={'meeting_uuid': meeting_uuid})

        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        def participant_joined_event_received(expected_caller_id_name):
            events = bus_events.accumulate(with_headers=True)
            assert_that(
                events,
                has_item(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                caller_id_name=expected_caller_id_name,
                            )
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_participant_joined',
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    )
                ),
            )

        until.assert_(participant_joined_event_received, 'participant1', timeout=10)

    def test_user_participant_joins_sends_event(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        meeting_bus_events = self.bus.accumulator(
            headers={'meeting_uuid': meeting_uuid}
        )
        call_bus_events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.given_call_in_meeting(
            MEETING1_EXTENSION, user_uuid=user_uuid, tenant_uuid=tenant_uuid
        )
        other_channel_id = self.given_call_in_meeting(
            MEETING1_EXTENSION, user_uuid=other_user_uuid, tenant_uuid=tenant_uuid
        )

        def user_participant_joined_event_received(first_user_uuid, second_user_uuid):
            assert_that(
                meeting_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'meeting_user_participant_joined',
                                'data': has_entries(
                                    {
                                        'user_uuid': first_user_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_user_participant_joined',
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                                f'user_uuid:{user_uuid}': True,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'meeting_user_participant_joined',
                                'data': has_entries(
                                    {
                                        'user_uuid': second_user_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_user_participant_joined',
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                                f'user_uuid:{user_uuid}': True,
                            }
                        ),
                    ),
                ),
            )
            assert_that(
                call_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_updated',
                                'data': has_entries(
                                    {
                                        'user_uuid': first_user_uuid,
                                        'talking_to': has_entries(
                                            {other_channel_id: second_user_uuid}
                                        ),
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'call_updated',
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    )
                ),
            )

        until.assert_(
            user_participant_joined_event_received,
            user_uuid,
            other_user_uuid,
            timeout=10,
        )

    def test_participant_leaves_sends_event(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, tenant_uuid=tenant_uuid, name='meeting'),
        )
        bus_events = self.bus.accumulator(headers={'meeting_uuid': meeting_uuid})

        channel_id = self.given_call_in_meeting(
            MEETING1_EXTENSION, caller_id_name='participant1'
        )

        self.ari.channels.hangup(channelId=channel_id)

        def participant_left_event_received(expected_caller_id_name):
            assert_that(
                bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                caller_id_name=expected_caller_id_name,
                            )
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_participant_left',
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    )
                ),
            )

        until.assert_(participant_left_event_received, 'participant1', timeout=10)

    def test_user_participant_leaves_sends_event(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        meeting_bus_events = self.bus.accumulator(
            headers={'meeting_uuid': meeting_uuid}
        )
        call_bus_events = self.bus.accumulator(headers={'name': 'call_updated'})

        channel_id = self.given_call_in_meeting(
            MEETING1_EXTENSION, user_uuid=user_uuid, tenant_uuid=tenant_uuid
        )
        other_channel_id = self.given_call_in_meeting(
            MEETING1_EXTENSION, user_uuid=other_user_uuid, tenant_uuid=tenant_uuid
        )

        def user_participant_left_event_received(expected_user_uuid):
            assert_that(
                meeting_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'meeting_user_participant_left',
                                'data': has_entries(
                                    {
                                        'user_uuid': expected_user_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_user_participant_left',
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                                f'user_uuid:{user_uuid}': True,
                            }
                        ),
                    ),
                ),
            )

        def call_updated_event_received():
            assert_that(
                call_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_updated',
                                'data': has_entries(
                                    {
                                        'user_uuid': user_uuid,
                                        'talking_to': empty(),
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': 'call_updated',
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    )
                ),
            )

        self.ari.channels.hangup(channelId=other_channel_id)

        until.assert_(user_participant_left_event_received, other_user_uuid, timeout=10)
        until.assert_(call_updated_event_received, timeout=10)

        self.ari.channels.hangup(channelId=channel_id)

        until.assert_(user_participant_left_event_received, user_uuid, timeout=10)

    def test_meeting_deleted_ends_confbridge(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        channel_id = self.given_call_in_meeting(MEETING1_EXTENSION, user_uuid=user_uuid)
        other_channel_id = self.given_call_in_meeting(
            MEETING1_EXTENSION, user_uuid=other_user_uuid
        )

        self.bus.send_meeting_deleted_event(meeting_uuid)

        def channels_left_meeting(*channel_ids):
            for channel_id in channel_ids:
                assert_that(
                    channel_id,
                    is_not(self.c.is_in_bridge()),
                    'Channel is still in meeting',
                )

        until.assert_(channels_left_meeting, channel_id, other_channel_id, timeout=5)

    def test_kick_participant_with_no_confd(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.meetings.kick_participant).with_args(
                    meeting_uuid, participant_id
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        }
                    )
                ),
            )

    def test_kick_participant_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(
                calling(self.calld_client.meetings.kick_participant).with_args(
                    meeting_uuid, participant['id']
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )

    def test_kick_participant_with_no_meetings(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        assert_that(
            calling(self.calld_client.meetings.kick_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )

    def test_kick_participant_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        participant_id = '12345.67'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        assert_that(
            calling(self.calld_client.meetings.kick_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    }
                )
            ),
        )

    def test_kick_participant_notfound(self):
        meeting_uuid = MEETING1_UUID
        wrong_participant_id = 'wrong-participant-id'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        assert_that(
            calling(self.calld_client.meetings.kick_participant).with_args(
                meeting_uuid, wrong_participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    }
                )
            ),
        )

    def test_kick_meeting_notfound(self):
        meeting_uuid = MEETING1_UUID
        wrong_meeting_uuid = 'wrong-meeting-uuid'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        assert_that(
            calling(self.calld_client.meetings.kick_participant).with_args(
                wrong_meeting_uuid, participant['id']
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )

    def test_kick_wrong_meeting(self):
        meeting_uuid = MEETING1_UUID
        wrong_meeting_uuid = EMPTY_MEETING_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
            MockMeeting(uuid=wrong_meeting_uuid, name='empty meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        assert_that(
            calling(self.calld_client.meetings.kick_participant).with_args(
                wrong_meeting_uuid, participant['id']
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    }
                )
            ),
        )

    def test_kick_wrong_participant(self):
        meeting1_uuid = MEETING1_UUID
        meeting2_uuid = MEETING2_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting1_uuid, name='meeting1'),
            MockMeeting(uuid=meeting2_uuid, name='meeting2'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_meeting(MEETING2_EXTENSION, caller_id_name='participant2')
        participants = self.calld_client.meetings.list_participants(meeting1_uuid)
        wrong_participant = participants['items'][0]

        assert_that(
            calling(self.calld_client.meetings.kick_participant).with_args(
                meeting2_uuid, wrong_participant['id']
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    }
                )
            ),
        )

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
            assert_that(participants, has_entries({'total': 0, 'items': empty()}))

        until.assert_(
            no_more_participants, timeout=10, message='Participant was not kicked'
        )

    def test_user_kick_participant_with_no_meetings(self):
        meeting_uuid = 14
        participant_id = '12345.67'
        user_uuid = make_user_uuid()
        calld_client = self.make_user_calld(user_uuid)

        assert_that(
            calling(calld_client.meetings.user_kick_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )

    def test_user_no_owner_kick_participant(self):
        meeting_uuid = MEETING1_UUID
        user_uuid = make_user_uuid()
        calld_client = self.make_user_calld(user_uuid)
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', owner_uuids=[]),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        assert_that(
            calling(calld_client.meetings.user_kick_participant).with_args(
                meeting_uuid, participant['id']
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )

    def test_user_kick_participant(self):
        meeting_uuid = MEETING1_UUID
        user_uuid = make_user_uuid()
        calld_client = self.make_user_calld(user_uuid)
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', owner_uuids=[user_uuid]),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]

        calld_client.meetings.user_kick_participant(meeting_uuid, participant['id'])

        def no_more_participants():
            participants = calld_client.meetings.list_participants(meeting_uuid)
            assert_that(participants, has_entries({'total': 0, 'items': empty()}))

        until.assert_(
            no_more_participants, timeout=10, message='Participant was not kicked'
        )

    @unittest.skip
    def test_mute_participant_with_no_confd(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.meetings.mute_participant).with_args(
                    meeting_uuid, participant_id
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        }
                    )
                ),
            )
            assert_that(
                calling(self.calld_client.meetings.unmute_participant).with_args(
                    meeting_uuid, participant_id
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        }
                    )
                ),
            )

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
            assert_that(
                calling(self.calld_client.meetings.mute_participant).with_args(
                    meeting_uuid, participant['id']
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )
            assert_that(
                calling(self.calld_client.meetings.unmute_participant).with_args(
                    meeting_uuid, participant['id']
                ),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )

    @unittest.skip
    def test_mute_participant_with_no_meetings(self):
        meeting_uuid = 14
        participant_id = '12345.67'

        assert_that(
            calling(self.calld_client.meetings.mute_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )
        assert_that(
            calling(self.calld_client.meetings.unmute_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )

    @unittest.skip
    def test_mute_participant_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        participant_id = '12345.67'
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        assert_that(
            calling(self.calld_client.meetings.mute_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    }
                )
            ),
        )
        assert_that(
            calling(self.calld_client.meetings.unmute_participant).with_args(
                meeting_uuid, participant_id
            ),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    }
                )
            ),
        )

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
            assert_that(
                participants,
                has_entries(
                    {'total': 1, 'items': contains_exactly(has_entry('muted', True))}
                ),
            )

        until.assert_(
            participant_is_muted, timeout=10, message='Participant was not muted'
        )

        self.calld_client.meetings.unmute_participant(meeting_uuid, participant['id'])

        def participant_is_not_muted():
            participants = self.calld_client.meetings.list_participants(meeting_uuid)
            assert_that(
                participants,
                has_entries(
                    {'total': 1, 'items': contains_exactly(has_entry('muted', False))}
                ),
            )

        until.assert_(
            participant_is_not_muted, timeout=10, message='Participant is still muted'
        )

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
        tenant_uuid = MEETING1_TENANT_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        self.given_call_in_meeting(
            MEETING1_EXTENSION, caller_id_name='participant1', tenant_uuid=tenant_uuid
        )
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        participant = participants['items'][0]
        mute_bus_events = self.bus.accumulator(headers={'meeting_uuid': meeting_uuid})

        self.calld_client.meetings.mute_participant(meeting_uuid, participant['id'])

        def participant_muted_event_received(muted):
            event_name = 'meeting_participant_unmuted'
            if muted:
                event_name = 'meeting_participant_muted'

            assert_that(
                mute_bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': event_name,
                                'data': has_entries(
                                    {
                                        'id': participant['id'],
                                        'meeting_uuid': meeting_uuid,
                                        'muted': muted,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': event_name,
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    )
                ),
            )

        until.assert_(
            participant_muted_event_received,
            muted=True,
            timeout=10,
            message='Mute event was not received',
        )

        self.calld_client.meetings.unmute_participant(meeting_uuid, participant['id'])

        until.assert_(
            participant_muted_event_received,
            muted=True,
            timeout=10,
            message='Unmute event was not received',
        )

    @unittest.skip
    def test_record_with_no_confd(self):
        meeting_uuid = 14

        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.meetings.record).with_args(meeting_uuid),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        }
                    )
                ),
            )
            assert_that(
                calling(self.calld_client.meetings.stop_record).with_args(meeting_uuid),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        }
                    )
                ),
            )

    @unittest.skip
    def test_record_with_no_amid(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        with self.amid_stopped():
            assert_that(
                calling(self.calld_client.meetings.record).with_args(meeting_uuid),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )
            assert_that(
                calling(self.calld_client.meetings.stop_record).with_args(meeting_uuid),
                raises(CalldError).matching(
                    has_properties(
                        {
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        }
                    )
                ),
            )

    @unittest.skip
    def test_record_with_no_meetings(self):
        meeting_uuid = 14

        assert_that(
            calling(self.calld_client.meetings.record).with_args(meeting_uuid),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )
        assert_that(
            calling(self.calld_client.meetings.stop_record).with_args(meeting_uuid),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 404,
                        'error_id': 'no-such-meeting',
                    }
                )
            ),
        )

    @unittest.skip
    def test_record_participant_with_no_participants(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )

        assert_that(
            calling(self.calld_client.meetings.record).with_args(meeting_uuid),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'meeting-has-no-participants',
                    }
                )
            ),
        )

    @unittest.skip
    def test_record(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting'),
        )
        self.given_call_in_meeting(MEETING1_EXTENSION, caller_id_name='participant1')

        def latest_record_file():
            record_files = self.docker_exec(
                ['ls', '-t', '/var/spool/asterisk/monitor'], 'ari'
            )
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
        assert_that(
            calling(self.calld_client.meetings.record).with_args(meeting_uuid),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'meeting-already-recorded',
                    }
                )
            ),
        )

        # stop record twice
        self.calld_client.meetings.stop_record(meeting_uuid)
        assert_that(
            calling(self.calld_client.meetings.stop_record).with_args(meeting_uuid),
            raises(CalldError).matching(
                has_properties(
                    {
                        'status_code': 400,
                        'error_id': 'meeting-not-recorded',
                    }
                )
            ),
        )

    @unittest.skip
    def test_record_send_events(self):
        meeting_uuid = MEETING1_UUID
        tenant_uuid = MEETING1_TENANT_UUID
        self.confd.set_meetings(
            MockMeeting(uuid=meeting_uuid, name='meeting', tenant_uuid=tenant_uuid),
        )
        self.given_call_in_meeting(
            MEETING1_EXTENSION, caller_id_name='participant1', tenant_uuid=tenant_uuid
        )
        record_bus_events = self.bus.accumulator(headers={'meeting_uuid': meeting_uuid})

        self.calld_client.meetings.record(meeting_uuid)

        def record_event_received(record):
            event_name = (
                'meeting_record_started' if record else 'meeting_record_stopped'
            )
            assert_that(
                record_bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': event_name,
                                'data': has_entries(
                                    {
                                        'id': meeting_uuid,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            {
                                'name': event_name,
                                'meeting_uuid': meeting_uuid,
                                'tenant_uuid': tenant_uuid,
                            }
                        ),
                    )
                ),
            )

        until.assert_(
            record_event_received,
            record=True,
            timeout=10,
            message='Record start event was not received',
        )

        self.calld_client.meetings.stop_record(meeting_uuid)

        until.assert_(
            record_event_received,
            record=False,
            timeout=10,
            message='Record stop event was not received',
        )

    @unittest.skip
    def test_participant_talking_sends_event(self):
        meeting_uuid = MEETING1_UUID
        self.confd.set_meetings(
            MockMeeting(
                uuid=meeting_uuid, name='meeting', tenant_uuid=MEETING1_TENANT_UUID
            ),
        )
        talking_user_uuid = 'talking-user-uuid'
        listening_user_uuid = 'listening-user-uuid'

        meeting_events = self.bus.accumulator(headers={'meeting_uuid': meeting_uuid})

        # listening user must enter the meeting first, to receive the event from the talking user
        self.given_call_in_meeting(
            MEETING1_EXTENSION,
            caller_id_name='participant2',
            user_uuid=listening_user_uuid,
        )
        self.given_call_in_meeting(
            MEETING1_EXTENSION,
            caller_id_name='participant1',
            user_uuid=talking_user_uuid,
        )
        participants = self.calld_client.meetings.list_participants(meeting_uuid)
        talking_participant = [
            participant
            for participant in participants['items']
            if participant['user_uuid'] == talking_user_uuid
        ][0]

        def talking_event_received(bus_events, talking):
            suffix = '_started' if talking else '_stopped'

            assert_that(
                bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                id=talking_participant['id'],
                                meeting_uuid=meeting_uuid,
                            )
                        ),
                        headers=has_entries(
                            name='meeting_participant_talk' + suffix,
                            tenant_uuid=MEETING1_TENANT_UUID,
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                id=talking_participant['id'],
                                meeting_uuid=meeting_uuid,
                            )
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_user_participant_talk' + suffix,
                                'tenant_uuid': MEETING1_TENANT_UUID,
                                f'user_uuid:{talking_user_uuid}': True,
                            }
                        ),
                    ),
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                id=talking_participant['id'],
                                meeting_uuid=meeting_uuid,
                            ),
                        ),
                        headers=has_entries(
                            {
                                'name': 'meeting_user_participant_talk' + suffix,
                                'tenant_uuid': MEETING1_TENANT_UUID,
                                f'user_uuid:{listening_user_uuid}': True,
                            }
                        ),
                    ),
                ),
            )

        until.assert_(talking_event_received, meeting_events, talking=True, timeout=10)

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
                },
            },
            headers={
                'name': 'ConfbridgeTalking',
            },
        )

        until.assert_(talking_event_received, meeting_events, talking=False, timeout=10)
