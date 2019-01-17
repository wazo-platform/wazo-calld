# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from ari.exceptions import ARINotFound
from hamcrest import (
    assert_that,
    calling,
    empty,
    equal_to,
    contains_inanyorder,
    has_entries,
    has_entry,
    has_properties,
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

    def test_list_participants_with_no_confd(self):
        ctid_ng = self.make_ctid_ng()
        wrong_id = 14

        with self.confd_stopped():
            assert_that(calling(ctid_ng.conferences.list_participants).with_args(wrong_id),
                        raises(CtidNGError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'xivo-confd-unreachable',
                        })))

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
