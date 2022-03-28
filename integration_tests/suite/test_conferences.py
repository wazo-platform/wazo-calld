# Copyright 2018-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid
import os

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
    less_than,
)
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError
from .helpers.confd import MockConference
from .helpers.constants import ENDPOINT_AUTOANSWER
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsteriskIntegrationTest

CONFERENCE1_EXTENSION = '4001'
CONFERENCE1_ID = 4001
CONFERENCE1_TENANT_UUID = '404afda0-36ba-43de-9571-a06c81b9c43e'


def make_user_uuid():
    return str(uuid.uuid4())


class TestConferences(RealAsteriskIntegrationTest):

    asset = 'real_asterisk_conference'

    def setUp(self):
        super().setUp()
        self.confd.reset()


class TestConferenceParticipants(TestConferences):

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)

    def given_call_in_conference(self, conference_extension, caller_id_name=None, user_uuid=None):
        caller_id_name = caller_id_name or 'caller for {}'.format(conference_extension)
        variables = {
            'CALLERID(name)': caller_id_name,
            'WAZO_TENANT_UUID': CONFERENCE1_TENANT_UUID,
        }
        if user_uuid:
            variables['XIVO_USERUUID'] = user_uuid
        channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='conferences',
            extension=CONFERENCE1_EXTENSION,
            variables={'variables': variables},
        )

        def channel_is_in_conference(channel):
            assert_that(channel.id, self.c.is_in_bridge(), 'Channel is not in conference')

        until.assert_(channel_is_in_conference, channel, timeout=10)
        return channel.id

    def test_list_participants_with_no_confd(self):
        wrong_id = 14

        with self.confd_stopped():
            assert_that(calling(self.calld_client.conferences.list_participants).with_args(wrong_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    def test_list_participants_with_no_amid(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )

        with self.amid_stopped():
            assert_that(calling(self.calld_client.conferences.list_participants).with_args(conference_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    def test_list_participants_with_no_conferences(self):
        wrong_id = 14

        assert_that(calling(self.calld_client.conferences.list_participants).with_args(wrong_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                    })))

    def test_list_participants_with_no_conference_with_that_id(self):
        user_uuid = 'user-uuid'
        conference_id = CONFERENCE1_ID
        other_conference_id = 42
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
            MockConference(id=other_conference_id, name='empty'),
        )
        self.given_call_in_conference(
            CONFERENCE1_EXTENSION,
            caller_id_name='participant1',
            user_uuid=user_uuid,
        )
        self.given_call_in_conference(
            CONFERENCE1_EXTENSION,
            caller_id_name='participant2',
        )

        participants = self.calld_client.conferences.list_participants(other_conference_id)

        assert_that(participants, has_entries(total=0, items=empty()))

    def test_list_participants_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )

        participants = self.calld_client.conferences.list_participants(conference_id)

        assert_that(participants, has_entries({
            'total': 0,
            'items': empty(),
        }))

    def test_user_list_participants_when_user_is_not_participant(self):
        user_uuid = 'user-uuid'
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        calld_client = self.make_user_calld(user_uuid)

        assert_that(calling(calld_client.conferences.user_list_participants).with_args(conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 403,
                        'error_id': 'user-not-participant',
                    })))

    def test_user_list_participants_when_user_is_participant(self):
        user_uuid = 'user-uuid'
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1', user_uuid=user_uuid)
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant2')
        calld_client = self.make_user_calld(user_uuid)

        participants = calld_client.conferences.user_list_participants(conference_id)

        assert_that(participants, has_entries({
            'total': 2,
            'items': contains_inanyorder(
                has_entry('caller_id_name', 'participant1'),
                has_entry('caller_id_name', 'participant2'),
            )
        }))

    def test_list_participants_with_two_participants(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant2')

        participants = self.calld_client.conferences.list_participants(conference_id)

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
            MockConference(
                id=conference_id,
                tenant_uuid=CONFERENCE1_TENANT_UUID,
                name='conference',
            ),
        )
        bus_events = self.bus.accumulator('conferences.{}.participants.joined'.format(conference_id))
        first_uuid = 'first-uuid'
        second_uuid = 'second-uuid'

        self.given_call_in_conference(CONFERENCE1_EXTENSION, user_uuid=first_uuid)
        self.given_call_in_conference(
            CONFERENCE1_EXTENSION, caller_id_name='participant1', user_uuid=second_uuid
        )

        def participant_joined_event_received(expected_caller_id_name):
            events = bus_events.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                caller_id_name=expected_caller_id_name
                            )
                        ),
                        headers=has_entries({
                            'name': 'conference_participant_joined',
                            'conference_id': conference_id,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                            f'user_uuid:{first_uuid}': True,
                            f'user_uuid:{second_uuid}': True,
                        })
                    )
                )
            )

        until.assert_(participant_joined_event_received, 'participant1', timeout=10)

    def test_user_participant_joins_sends_event(self):
        conference_id = CONFERENCE1_ID
        tenant_uuid = CONFERENCE1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference', tenant_uuid=tenant_uuid),
        )
        conference_bus_events = self.bus.accumulator('conferences.users.{}.participants.joined'.format(user_uuid))
        call_bus_events = self.bus.accumulator('calls.call.updated')

        self.given_call_in_conference(CONFERENCE1_EXTENSION, user_uuid=user_uuid)
        other_channel_id = self.given_call_in_conference(CONFERENCE1_EXTENSION, user_uuid=other_user_uuid)

        def user_participant_joined_event_received(first_user_uuid, second_user_uuid):
            assert_that(
                conference_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries({
                            'name': 'conference_user_participant_joined',
                            'data': has_entries({
                                'user_uuid': first_user_uuid,
                            })
                        }),
                        headers=has_entries({
                            'name': 'conference_user_participant_joined',
                            'conference_id': CONFERENCE1_ID,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                            f'user_uuid:{user_uuid}': True
                        })
                    ),
                    has_entries(
                        message=has_entries({
                            'name': 'conference_user_participant_joined',
                            'data': has_entries({
                                'user_uuid': second_user_uuid,
                            })
                        }),
                        headers=has_entries({
                            'name': 'conference_user_participant_joined',
                            'conference_id': CONFERENCE1_ID,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                            f'user_uuid:{user_uuid}': True
                        })
                    )
                )
            )
            assert_that(
                call_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries({
                            'name': 'call_updated',
                            'data': has_entries({
                                'user_uuid': first_user_uuid,
                                'talking_to': has_entries({
                                    other_channel_id: second_user_uuid
                                })
                            })
                        }),
                        headers=has_entries({
                            'name': 'call_updated',
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                        })
                    )
                )
            )

        until.assert_(user_participant_joined_event_received, user_uuid, other_user_uuid, timeout=10)

    def test_participant_leaves_sends_event(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(
                id=conference_id,
                tenant_uuid=CONFERENCE1_TENANT_UUID,
                name='conference',
            ),
        )
        bus_events = self.bus.accumulator('conferences.{}.participants.left'.format(conference_id))
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'

        channel_id = self.given_call_in_conference(
            CONFERENCE1_EXTENSION,
            caller_id_name='participant1',
            user_uuid=user_uuid,
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, user_uuid=other_user_uuid)

        self.ari.channels.hangup(channelId=channel_id)

        def participant_left_event_received(expected_caller_id_name):
            events = bus_events.accumulate(with_headers=True)
            assert_that(
                events,
                has_items(
                    has_entries(
                        message=has_entries(
                            data=has_entries(
                                caller_id_name=expected_caller_id_name
                            )
                        ),
                        headers=has_entries({
                            'name': 'conference_participant_left',
                            'conference_id': conference_id,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                            f'user_uuid:{user_uuid}': True,
                            f'user_uuid:{other_user_uuid}': True,
                        })
                    )
                )
            )

        until.assert_(participant_left_event_received, 'participant1', timeout=10)

    def test_user_participant_leaves_sends_event(self):
        conference_id = CONFERENCE1_ID
        tenant_uuid = CONFERENCE1_TENANT_UUID
        user_uuid = make_user_uuid()
        other_user_uuid = 'another-uuid'
        self.confd.set_conferences(
            MockConference(
                id=conference_id,
                name='conference',
                tenant_uuid=tenant_uuid,
            )
        )
        conference_bus_events = self.bus.accumulator('conferences.users.{}.participants.left'.format(user_uuid))
        call_bus_events = self.bus.accumulator('calls.call.updated')

        channel_id = self.given_call_in_conference(CONFERENCE1_EXTENSION, user_uuid=user_uuid)
        other_channel_id = self.given_call_in_conference(CONFERENCE1_EXTENSION, user_uuid=other_user_uuid)

        def user_participant_left_event_received(expected_user_uuid):
            assert_that(
                conference_bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'conference_user_participant_left',
                            'data': has_entries({
                                'user_uuid': expected_user_uuid,
                            })
                        }),
                        headers=has_entries({
                            'name': 'conference_user_participant_left',
                            'conference_id': conference_id,
                            'tenant_uuid': tenant_uuid,
                            f'user_uuid:{user_uuid}': True,
                        })
                    )
                )
            )

        def call_updated_event_received():
            assert_that(
                call_bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_updated',
                            'data': has_entries({
                                'user_uuid': user_uuid,
                                'talking_to': empty(),
                            })
                        }),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=CONFERENCE1_TENANT_UUID,
                        )
                    )
                )
            )

        self.ari.channels.hangup(channelId=other_channel_id)

        until.assert_(user_participant_left_event_received, other_user_uuid, timeout=10)
        until.assert_(call_updated_event_received, timeout=10)

        self.ari.channels.hangup(channelId=channel_id)

        until.assert_(user_participant_left_event_received, user_uuid, timeout=10)

    def test_kick_participant_with_no_confd(self):
        conference_id = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(calling(self.calld_client.conferences.kick_participant)
                        .with_args(conference_id, participant_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    def test_kick_participant_with_no_amid(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(calling(self.calld_client.conferences.kick_participant)
                        .with_args(conference_id, participant['id']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    def test_kick_participant_with_no_conferences(self):
        conference_id = 14
        participant_id = '12345.67'

        assert_that(calling(self.calld_client.conferences.kick_participant)
                    .with_args(conference_id, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))

    def test_kick_participant_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        participant_id = '12345.67'
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )

        assert_that(calling(self.calld_client.conferences.kick_participant)
                    .with_args(conference_id, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))

    def test_kick_participant(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        self.calld_client.conferences.kick_participant(conference_id, participant['id'])

        def no_more_participants():
            participants = self.calld_client.conferences.list_participants(conference_id)
            assert_that(participants, has_entries({
                'total': 0,
                'items': empty()
            }))
        until.assert_(no_more_participants, timeout=10, message='Participant was not kicked')

    def test_mute_participant_with_no_confd(self):
        conference_id = 14
        participant_id = '12345.67'

        with self.confd_stopped():
            assert_that(calling(self.calld_client.conferences.mute_participant)
                        .with_args(conference_id, participant_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))
            assert_that(calling(self.calld_client.conferences.unmute_participant)
                        .with_args(conference_id, participant_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    def test_mute_participant_with_no_amid(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        with self.amid_stopped():
            assert_that(calling(self.calld_client.conferences.mute_participant)
                        .with_args(conference_id, participant['id']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))
            assert_that(calling(self.calld_client.conferences.unmute_participant)
                        .with_args(conference_id, participant['id']),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    def test_mute_participant_with_no_conferences(self):
        conference_id = 14
        participant_id = '12345.67'

        assert_that(calling(self.calld_client.conferences.mute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))
        assert_that(calling(self.calld_client.conferences.unmute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))

    def test_mute_participant_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        participant_id = '12345.67'
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )

        assert_that(calling(self.calld_client.conferences.mute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))
        assert_that(calling(self.calld_client.conferences.unmute_participant)
                    .with_args(conference_id, participant_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-participant',
                    })))

    def test_mute_unmute_participant(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        self.calld_client.conferences.mute_participant(conference_id, participant['id'])

        def participant_is_muted():
            participants = self.calld_client.conferences.list_participants(conference_id)
            assert_that(participants, has_entries({
                'total': 1,
                'items': contains_exactly(has_entry('muted', True))
            }))
        until.assert_(participant_is_muted, timeout=10, message='Participant was not muted')

        self.calld_client.conferences.unmute_participant(conference_id, participant['id'])

        def participant_is_not_muted():
            participants = self.calld_client.conferences.list_participants(conference_id)
            assert_that(participants, has_entries({
                'total': 1,
                'items': contains_exactly(has_entry('muted', False))
            }))
        until.assert_(participant_is_not_muted, timeout=10, message='Participant is still muted')

    def test_mute_unmute_participant_twice(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        participants = self.calld_client.conferences.list_participants(conference_id)
        participant = participants['items'][0]

        self.calld_client.conferences.mute_participant(conference_id, participant['id'])
        self.calld_client.conferences.mute_participant(conference_id, participant['id'])

        # no error

        self.calld_client.conferences.unmute_participant(conference_id, participant['id'])
        self.calld_client.conferences.unmute_participant(conference_id, participant['id'])

        # no error

    def test_mute_unmute_participant_send_events(self):
        conference_id = CONFERENCE1_ID
        user_uuid = make_user_uuid()
        self.confd.set_conferences(
            MockConference(
                id=conference_id,
                name='conference',
                tenant_uuid=CONFERENCE1_TENANT_UUID,
            ),
        )
        self.given_call_in_conference(
            CONFERENCE1_EXTENSION,
            caller_id_name='participant1',
            user_uuid=user_uuid
        )
        participants = self.calld_client.conferences.list_participants(conference_id)
        participant = participants['items'][0]
        mute_bus_events = self.bus.accumulator('conferences.{}.participants.mute'.format(conference_id))

        self.calld_client.conferences.mute_participant(conference_id, participant['id'])

        def participant_muted_event_received(muted):
            assert_that(
                mute_bus_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries({
                            'name': 'conference_participant_muted' if muted else 'conference_participant_unmuted',
                            'data': has_entries({
                                'id': participant['id'],
                                'conference_id': conference_id,
                                'muted': muted,
                            })
                        }),
                        headers=has_entries({
                            'name': 'conference_participant_muted' if muted else 'conference_participant_unmuted',
                            'conference_id': conference_id,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                        }),
                    )
                )
            )

        until.assert_(participant_muted_event_received, muted=True, timeout=10, message='Mute event was not received')

        self.calld_client.conferences.unmute_participant(conference_id, participant['id'])

        until.assert_(participant_muted_event_received, muted=True, timeout=10, message='Unmute event was not received')

    def test_record_with_no_confd(self):
        conference_id = 14

        with self.confd_stopped():
            assert_that(calling(self.calld_client.conferences.record)
                        .with_args(conference_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))
            assert_that(calling(self.calld_client.conferences.stop_record)
                        .with_args(conference_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-confd-unreachable',
                        })))

    def test_record_with_no_amid(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        with self.amid_stopped():
            assert_that(calling(self.calld_client.conferences.record)
                        .with_args(conference_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))
            assert_that(calling(self.calld_client.conferences.stop_record)
                        .with_args(conference_id),
                        raises(CalldError).matching(has_properties({
                            'status_code': 503,
                            'error_id': 'wazo-amid-error',
                        })))

    def test_record_with_no_conferences(self):
        conference_id = 14

        assert_that(calling(self.calld_client.conferences.record)
                    .with_args(conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))
        assert_that(calling(self.calld_client.conferences.stop_record)
                    .with_args(conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'no-such-conference',
                    })))

    def test_record_participant_with_no_participants(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )

        assert_that(calling(self.calld_client.conferences.record)
                    .with_args(conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'conference-has-no-participants',
                    })))

    def test_record(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        def latest_record_file():
            record_files = self.docker_exec(['ls', '-t', '/var/spool/asterisk/monitor'], 'ari')
            latest_record_file = record_files.split(b'\n')[0].decode('utf-8')
            return os.path.join('/var/spool/asterisk/monitor', latest_record_file)

        def file_size(file_path):
            return int(self.docker_exec(['stat', '-c', '%s', file_path], 'ari').strip())

        self.calld_client.conferences.record(conference_id)
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

        self.calld_client.conferences.stop_record(conference_id)
        assert_that(record_file_is_closed(), is_(True))

    def test_record_twice(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(id=conference_id, name='conference'),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')

        # record twice
        self.calld_client.conferences.record(conference_id)
        assert_that(calling(self.calld_client.conferences.record)
                    .with_args(conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'conference-already-recorded',
                    })))

        # stop record twice
        self.calld_client.conferences.stop_record(conference_id)
        assert_that(calling(self.calld_client.conferences.stop_record)
                    .with_args(conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'conference-not-recorded',
                    })))

    def test_record_send_events(self):
        conference_id = CONFERENCE1_ID
        tenant_uuid = CONFERENCE1_TENANT_UUID
        self.confd.set_conferences(
            MockConference(
                id=conference_id,
                name='conference',
                tenant_uuid=tenant_uuid,
            ),
        )
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1')
        record_bus_events = self.bus.accumulator('conferences.{}.record'.format(conference_id))

        self.calld_client.conferences.record(conference_id)

        def record_event_received(record):
            assert_that(
                record_bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'conference_record_started' if record else 'conference_record_stopped',
                            'data': has_entries({
                                'id': conference_id,
                            })
                        }),
                        headers=has_entries({
                            'name': 'conference_record_started' if record else 'conference_record_stopped',
                            'conference_id': conference_id,
                            'tenant_uuid': tenant_uuid,
                        })
                    )
                )
            )

        until.assert_(record_event_received, record=True, timeout=10, message='Record start event was not received')

        self.calld_client.conferences.stop_record(conference_id)

        until.assert_(record_event_received, record=False, timeout=10, message='Record stop event was not received')

    def test_participant_talking_sends_event(self):
        conference_id = CONFERENCE1_ID
        self.confd.set_conferences(
            MockConference(
                id=conference_id,
                name='conference',
                tenant_uuid=CONFERENCE1_TENANT_UUID,
            ),
        )
        talking_user_uuid = 'talking-user-uuid'
        listening_user_uuid = 'listening-user-uuid'

        admin_bus_events = self.bus.accumulator(f'conferences.{conference_id}.participants.talk')
        talking_user_bus_events = self.bus.accumulator(f'conferences.users.{talking_user_uuid}.participants.talk')
        listening_user_bus_events = self.bus.accumulator(f'conferences.users.{listening_user_uuid}.participants.talk')

        # listening user must enter the conference first, to receive the event from the talking user
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant2', user_uuid=listening_user_uuid)
        self.given_call_in_conference(CONFERENCE1_EXTENSION, caller_id_name='participant1', user_uuid=talking_user_uuid)
        participants = self.calld_client.conferences.list_participants(conference_id)
        talking_participant = [participant for participant in participants['items'] if participant['user_uuid'] == talking_user_uuid][0]

        def talking_event_received(bus_events, talking):
            event_name = 'conference_participant_talk_stopped'
            if talking:
                event_name = 'conference_participant_talk_started'

            assert_that(
                bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': event_name,
                            'data': has_entries({
                                'id': talking_participant['id'],
                                'conference_id': conference_id,
                            })
                        }),
                        headers=has_entries({
                            'name': event_name,
                            'conference_id': conference_id,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                            f'user_uuid:{talking_user_uuid}': True,
                            f'user_uuid:{listening_user_uuid}': True,
                        })
                    )
                )
            )

        def talking_user_event_received(bus_events, user_uuid, talking):
            event_name = 'conference_user_participant_talk_started'
            if not talking:
                event_name = 'conference_user_participant_talk_stopped'

            assert_that(
                bus_events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': event_name,
                            'data': has_entries({
                                'id': talking_participant['id'],
                                'conference_id': conference_id,
                            })
                        }),
                        headers=has_entries({
                            'name': event_name,
                            'conference_id': conference_id,
                            'tenant_uuid': CONFERENCE1_TENANT_UUID,
                            f'user_uuid:{user_uuid}': True,
                        })
                    )
                )
            )

        until.assert_(talking_event_received, admin_bus_events, talking=True, timeout=10)
        until.assert_(talking_user_event_received, talking_user_bus_events, talking_user_uuid, talking=True, timeout=10)
        until.assert_(talking_user_event_received, listening_user_bus_events, listening_user_uuid, talking=True, timeout=10)

        # send fake "stopped talking" AMI event
        self.bus.publish(
            {
                'name': 'ConfbridgeTalking',
                'data': {
                    'Event': 'ConfbridgeTalking',
                    'Conference': f'wazo-conference-{conference_id}',
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
        until.assert_(talking_user_event_received, talking_user_bus_events, talking_user_uuid, talking=False)
        until.assert_(talking_user_event_received, listening_user_bus_events, listening_user_uuid, talking=False)
