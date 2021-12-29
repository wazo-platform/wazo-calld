# Copyright 2020-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


import uuid

from hamcrest import (
    anything,
    assert_that,
    calling,
    equal_to,
    has_entries,
    has_item,
    has_items,
    has_length,
    has_properties,
)
from wazo_test_helpers.hamcrest.raises import raises
from wazo_test_helpers import until
from wazo_calld_client.exceptions import CalldError
from .helpers.auth import MockUserToken
from .helpers.base import make_user_uuid
from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.constants import (
    SOME_CALL_ID,
    INVALID_ACL_TOKEN,
    VALID_TOKEN,
)
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsterisk

SOME_ADHOC_CONFERENCE_ID = 'some-adhoc-conference-id'


class TestAdhocConference(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)
        calld_client = self.make_calld(token=VALID_TOKEN)
        self.real_asterisk = RealAsterisk(self.ari, calld_client)

    def make_user_token(self, user_uuid, tenant_uuid=None):
        token_id = str(uuid.uuid4())
        tenant_uuid = tenant_uuid or str(uuid.uuid4())
        self.auth.set_token(MockUserToken(token_id, tenant_uuid=tenant_uuid, user_uuid=user_uuid))
        return token_id

    def adhoc_conference_events_for_user(self, user_uuid):
        return self.bus.accumulator('conferences.users.{}.adhoc.#'.format(user_uuid))

    def given_adhoc_conference(self, *user_uuids, participant_count):
        participant_call_ids = []
        user_uuids = list(user_uuids)

        host_uuid = user_uuids.pop(0)
        try:
            participant_uuid = user_uuids.pop(0)
        except IndexError:
            participant_uuid = None
        host_call_id, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid, callee_uuid=participant_uuid)
        participant_call_ids.append(participant_call_id)

        for _ in range(participant_count - 1):
            try:
                participant_uuid = user_uuids.pop(0)
            except IndexError:
                participant_uuid = None
            _, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid, callee_uuid=participant_uuid)
            participant_call_ids.append(participant_call_id)

        host_events = self.bus.accumulator('conferences.users.{}.adhoc.#'.format(host_uuid))
        calld_client = self.make_user_calld(host_uuid)
        adhoc_conference = calld_client.adhoc_conferences.create_from_user(
            host_call_id,
            *participant_call_ids
        )

        def adhoc_conference_complete():
            join_events = [event for event in host_events.accumulate() if event['name'] == 'conference_adhoc_participant_joined']
            assert_that(join_events, has_length(participant_count + 2))
        until.assert_(adhoc_conference_complete, timeout=10)

        return adhoc_conference['conference_id'], [host_call_id] + participant_call_ids

    def test_user_create_adhoc_conference_no_auth(self):
        calld_no_auth = self.make_calld(token=INVALID_ACL_TOKEN)
        assert_that(calling(calld_no_auth.adhoc_conferences.create_from_user)
                    .with_args(SOME_CALL_ID, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 401,
                        'error_id': 'unauthorized',
                    })))

    def test_user_create_adhoc_conference_no_host_call(self):
        caller_call_id, callee_call_id = self.real_asterisk.given_bridged_call_stasis()

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(SOME_CALL_ID, callee_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'host-call-not-found',
                    })))

    def test_user_create_adhoc_conference_no_participant_call(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        caller_call_id, callee_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid)

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(caller_call_id, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_create_adhoc_conference_user_does_not_own_host_call(self):
        user_uuid = make_user_uuid()
        another_user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)

        self.calld_client.set_token(token)
        host_call_id, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=another_user_uuid)

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(host_call_id, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'host-call-not-found',
                    })))

    def test_user_create_adhoc_conference_invalid_request(self):
        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(None, None),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'invalid-data',
                    })))

    def test_user_create_adhoc_conference_correct(self):
        host_uuid = make_user_uuid()
        participant1_uuid = make_user_uuid()
        participant2_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        host_events = self.adhoc_conference_events_for_user(host_uuid)

        host_call1_id, participant1_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid, callee_uuid=participant1_uuid)
        host_call2_id, participant2_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid, callee_uuid=participant2_uuid)
        host_caller_id_num = "6845"
        self.ari.channels.setChannelVar(channelId=host_call1_id, variable='CALLERID(num)', value=host_caller_id_num)

        adhoc_conference = self.calld_client.adhoc_conferences.create_from_user(
            host_call1_id,
            participant1_call_id,
            participant2_call_id,
        )

        assert_that(adhoc_conference, has_entries({
            'conference_id': anything(),
        }))

        def calls_are_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call1_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                    participant2_call_id: anything(),
                })
            }))
            assert_that(host_call2_id, self.c.is_hungup())
        until.assert_(calls_are_bridged, timeout=10)

        def callerid_are_correct():
            host_connected_line = self.ari.channels.getChannelVar(channelId=host_call1_id, variable='CONNECTEDLINE(all)')['value']
            assert_that(host_connected_line, equal_to('"Conference" <6845>'))
        until.assert_(callerid_are_correct, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_created',
                            'data': {
                                'conference_id': adhoc_conference['conference_id'],
                            }})))
            assert_that(host_events.accumulate(), has_items(
                has_entries({
                    'name': 'conference_adhoc_participant_joined',
                    'data': has_entries({
                        'conference_id': adhoc_conference['conference_id'],
                        'call_id': participant1_call_id,
                    })
                }),
                has_entries({
                    'name': 'conference_adhoc_participant_joined',
                    'data': has_entries({
                        'conference_id': adhoc_conference['conference_id'],
                        'call_id': participant2_call_id,
                    })
                }),
            ))
        until.assert_(bus_events_are_sent, timeout=10)

    def test_user_create_adhoc_conference_participant_in_conference_with_host(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(user_uuid, participant_count=2)
        host_call_id, participant_call_id, _ = call_ids

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(host_call_id, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 409,
                        'error_id': 'host-already-in-conference',
                    })))

    def test_user_create_adhoc_conference_participant_not_in_stasis(self):
        host_uuid = make_user_uuid()
        participant1_uuid = make_user_uuid()
        participant2_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)

        host_call1_id, participant1_call_id = self.real_asterisk.given_bridged_call_not_stasis(caller_uuid=host_uuid, callee_uuid=participant1_uuid)
        host_call2_id, participant2_call_id = self.real_asterisk.given_bridged_call_not_stasis(caller_uuid=host_uuid, callee_uuid=participant2_uuid)

        adhoc_conference = self.calld_client.adhoc_conferences.create_from_user(
            host_call1_id,
            participant1_call_id,
            participant2_call_id,
        )

        assert_that(adhoc_conference, has_entries({
            'conference_id': anything(),
        }))

        def calls_are_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call1_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                    participant2_call_id: anything(),
                })
            }))
            assert_that(host_call2_id, self.c.is_hungup())
        until.assert_(calls_are_bridged, timeout=10)

    def test_user_create_adhoc_conference_participant_not_talking_to_host(self):
        host_uuid = make_user_uuid()
        another_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        host_call_id, participant1_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid)
        _, participant2_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=another_uuid)

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(host_call_id, participant1_call_id, participant2_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_create_adhoc_conference_with_host_lone_channel(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        _, participant1_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid)
        lone_call_id = self.real_asterisk.stasis_channel().id

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(lone_call_id, participant1_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'host-call-not-found',
                    })))

    def test_user_create_adhoc_conference_with_participant_lone_channel(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        host_call_id, participant1_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid)
        lone_call_id = self.real_asterisk.stasis_channel().id

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(host_call_id, participant1_call_id, lone_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_delete_adhoc_conference_no_auth(self):
        calld_no_auth = self.make_calld(token=INVALID_ACL_TOKEN)
        assert_that(calling(calld_no_auth.adhoc_conferences.delete_from_user)
                    .with_args(SOME_ADHOC_CONFERENCE_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 401,
                        'error_id': 'unauthorized',
                    })))

    def test_user_delete_adhoc_conference_no_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)

        assert_that(calling(self.calld_client.adhoc_conferences.delete_from_user)
                    .with_args(SOME_ADHOC_CONFERENCE_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'adhoc-conference-not-found',
                    })))

    def test_user_delete_adhoc_conference_user_does_not_own_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, _ = self.given_adhoc_conference(user_uuid, participant_count=1)
        another_user_uuid = make_user_uuid()
        another_token = self.make_user_token(another_user_uuid)
        self.calld_client.set_token(another_token)

        # response should not be different than a non-existing adhoc conference
        # to avoid malicious adhoc conference discovery
        assert_that(calling(self.calld_client.adhoc_conferences.delete_from_user)
                    .with_args(adhoc_conference_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'adhoc-conference-not-found',
                    })))

    def test_user_delete_adhoc_conference_correct(self):
        host_uuid = make_user_uuid()
        participant_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant_uuid, participant_count=1)
        host_call_id, participant_call_id = call_ids
        host_events = self.bus.accumulator('conferences.users.{}.adhoc.#'.format(host_uuid))

        self.calld_client.adhoc_conferences.delete_from_user(adhoc_conference_id)

        def calls_are_hungup():
            assert_that(host_call_id, self.c.is_hungup())
            assert_that(participant_call_id, self.c.is_hungup())
        until.assert_(calls_are_hungup, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_deleted',
                            'data': {
                                'conference_id': adhoc_conference_id,
                            }})))
            assert_that(host_events.accumulate(), has_items(
                has_entries({
                    'name': 'conference_adhoc_participant_left',
                    'data': has_entries({
                        'conference_id': adhoc_conference_id,
                        'call_id': participant_call_id,
                    })
                }),
                has_entries({
                    'name': 'conference_adhoc_participant_left',
                    'data': has_entries({
                        'conference_id': adhoc_conference_id,
                        'call_id': host_call_id,
                    })
                }),
            ))
        until.assert_(bus_events_are_sent, timeout=10)

    def test_extra_participant_hangup(self):
        host_uuid = make_user_uuid()
        participant1_uuid = make_user_uuid()
        participant2_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant1_uuid, participant2_uuid, participant_count=2)
        host_call_id, participant1_call_id, participant2_call_id = call_ids
        host_events = self.adhoc_conference_events_for_user(host_uuid)
        participant1_events = self.adhoc_conference_events_for_user(participant1_uuid)

        self.ari.channels.hangup(channelId=participant2_call_id)

        def calls_are_still_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                })
            }))
            assert_that(participant2_call_id, self.c.is_hungup())
        until.assert_(calls_are_still_bridged, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_participant_left',
                            'data': has_entries({
                                'conference_id': adhoc_conference_id,
                                'call_id': participant2_call_id,
                            })})))
            assert_that(participant1_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_participant_left',
                            'data': has_entries({
                                'conference_id': adhoc_conference_id,
                                'call_id': participant2_call_id,
                            })})))
        until.assert_(bus_events_are_sent, timeout=10)

    def test_last_participant_hangup(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(user_uuid, participant_count=1)
        host_call_id, participant1_call_id = call_ids
        host_events = self.adhoc_conference_events_for_user(user_uuid)

        self.ari.channels.hangup(channelId=participant1_call_id)

        def calls_are_hungup():
            assert_that(host_call_id, self.c.is_hungup())
            assert_that(participant1_call_id, self.c.is_hungup())
        until.assert_(calls_are_hungup, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_deleted',
                            'data': {
                                'conference_id': adhoc_conference_id,
                            }})))
        until.assert_(bus_events_are_sent, timeout=10)

    def test_host_hangup(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(user_uuid, participant_count=2)
        host_call_id, participant1_call_id, participant2_call_id = call_ids
        host_events = self.adhoc_conference_events_for_user(user_uuid)

        self.ari.channels.hangup(channelId=host_call_id)

        def calls_are_hungup():
            assert_that(host_call_id, self.c.is_hungup())
            assert_that(participant1_call_id, self.c.is_hungup())
            assert_that(participant2_call_id, self.c.is_hungup())
        until.assert_(calls_are_hungup, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_deleted',
                            'data': {
                                'conference_id': adhoc_conference_id,
                            }})))
        until.assert_(bus_events_are_sent, timeout=10)

    def test_user_add_participant_no_auth(self):
        calld_no_auth = self.make_calld(token=INVALID_ACL_TOKEN)
        assert_that(calling(calld_no_auth.adhoc_conferences.add_participant_from_user)
                    .with_args(SOME_CALL_ID, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 401,
                        'error_id': 'unauthorized',
                    })))

    def test_user_add_participant_no_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        host_call_id, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)

        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(SOME_ADHOC_CONFERENCE_ID, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'adhoc-conference-not-found',
                    })))

    def test_user_add_participant_no_call(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(user_uuid, participant_count=1)

        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(adhoc_conference_id, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_add_participant_user_does_not_own_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, _ = self.given_adhoc_conference(user_uuid, participant_count=1)
        _, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)
        another_user_uuid = make_user_uuid()
        another_token = self.make_user_token(another_user_uuid)
        self.calld_client.set_token(another_token)

        # response should not be different than a non-existing adhoc conference
        # to avoid malicious adhoc conference discovery
        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(adhoc_conference_id, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'adhoc-conference-not-found',
                    })))

    def test_user_add_participant_correct(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant_count=1)
        host_call1_id, participant1_call_id = call_ids
        participant2_uuid = make_user_uuid()
        host_call2_id, participant2_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=host_uuid, callee_uuid=participant2_uuid)
        host_events = self.adhoc_conference_events_for_user(host_uuid)
        host_connected_line_before = self.ari.channels.getChannelVar(channelId=host_call1_id, variable='CONNECTEDLINE(all)')['value']

        self.calld_client.adhoc_conferences.add_participant_from_user(adhoc_conference_id, participant2_call_id)

        def calls_are_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call1_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                    participant2_call_id: anything(),
                })
            }))
            assert_that(host_call2_id, self.c.is_hungup())
        until.assert_(calls_are_bridged, timeout=10)

        def callerid_are_correct():
            host_connected_line = self.ari.channels.getChannelVar(channelId=host_call1_id, variable='CONNECTEDLINE(all)')['value']
            assert_that(host_connected_line, equal_to(host_connected_line_before))
        until.assert_(callerid_are_correct, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(), has_items(
                has_entries({
                    'name': 'conference_adhoc_participant_joined',
                    'data': has_entries({
                        'conference_id': adhoc_conference_id,
                        'call_id': participant2_call_id,
                    })
                }),
            ))
        until.assert_(bus_events_are_sent, timeout=10)

    def test_user_add_participant_not_in_stasis(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant_count=1)
        host_call1_id, participant1_call_id = call_ids
        host_call2_id, participant2_call_id = self.real_asterisk.given_bridged_call_not_stasis(caller_uuid=host_uuid)

        self.calld_client.adhoc_conferences.add_participant_from_user(adhoc_conference_id, participant2_call_id)

        def calls_are_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call1_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                    participant2_call_id: anything(),
                })
            }))
            assert_that(host_call2_id, self.c.is_hungup())
        until.assert_(calls_are_bridged, timeout=10)

    def test_user_add_participant_lone_channel(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant_count=1)
        host_call_id, participant_call_id = call_ids
        lone_call_id = self.real_asterisk.stasis_channel().id

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(adhoc_conference_id, lone_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_add_participant_not_talking_to_host(self):
        host_uuid = make_user_uuid()
        another_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant_count=1)
        _, participant2_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=another_uuid)

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(adhoc_conference_id, participant2_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_add_participant_already_in_same_adhoc_conf(self):
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant_count=2)
        host_call_id, participant1_call_id, _ = call_ids

        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(adhoc_conference_id, participant1_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 409,
                        'error_id': 'participant-already-in-conference',
                    })))

    def test_user_add_participant_already_in_another_adhoc_conf(self):
        another_uuid = make_user_uuid()
        token = self.make_user_token(another_uuid)
        self.calld_client.set_token(token)
        _, call_ids = self.given_adhoc_conference(another_uuid, participant_count=2)
        host_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, _ = self.given_adhoc_conference(host_uuid, participant_count=2)
        _, participant1_call_id, __ = call_ids

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.add_participant_from_user)
                    .with_args(adhoc_conference_id, participant1_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_remove_participant_no_auth(self):
        calld_no_auth = self.make_calld(token=INVALID_ACL_TOKEN)
        assert_that(calling(calld_no_auth.adhoc_conferences.remove_participant_from_user)
                    .with_args(SOME_CALL_ID, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 401,
                        'error_id': 'unauthorized',
                    })))

    def test_user_remove_participant_no_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        host_call_id, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)

        assert_that(calling(self.calld_client.adhoc_conferences.remove_participant_from_user)
                    .with_args(SOME_ADHOC_CONFERENCE_ID, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'adhoc-conference-not-found',
                    })))

    def test_user_remove_participant_no_call(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(user_uuid, participant_count=1)

        assert_that(calling(self.calld_client.adhoc_conferences.remove_participant_from_user)
                    .with_args(adhoc_conference_id, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_remove_participant_not_in_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(user_uuid, participant_count=1)
        host_call_id, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)

        # response should not be different than a non-existing call, to avoid malicious call discovery
        assert_that(calling(self.calld_client.adhoc_conferences.remove_participant_from_user)
                    .with_args(adhoc_conference_id, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))

    def test_user_remove_participant_user_does_not_own_adhoc_conference(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, _ = self.given_adhoc_conference(user_uuid, participant_count=1)
        _, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)
        another_user_uuid = make_user_uuid()
        another_token = self.make_user_token(another_user_uuid)
        self.calld_client.set_token(another_token)

        # response should not be different than a non-existing adhoc conference
        # to avoid malicious adhoc conference discovery
        assert_that(calling(self.calld_client.adhoc_conferences.remove_participant_from_user)
                    .with_args(adhoc_conference_id, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 404,
                        'error_id': 'adhoc-conference-not-found',
                    })))

    def test_user_remove_participant_correct(self):
        host_uuid = make_user_uuid()
        participant1_uuid = make_user_uuid()
        participant2_uuid = make_user_uuid()
        token = self.make_user_token(host_uuid)
        self.calld_client.set_token(token)
        adhoc_conference_id, call_ids = self.given_adhoc_conference(host_uuid, participant1_uuid, participant2_uuid, participant_count=2)
        host_call_id, participant1_call_id, participant2_call_id = call_ids
        host_events = self.adhoc_conference_events_for_user(host_uuid)
        participant1_events = self.adhoc_conference_events_for_user(participant1_uuid)

        self.calld_client.adhoc_conferences.remove_participant_from_user(adhoc_conference_id, participant2_call_id)

        def calls_are_still_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                })
            }))
            assert_that(participant2_call_id, self.c.is_hungup())
        until.assert_(calls_are_still_bridged, timeout=10)

        def bus_events_are_sent():
            assert_that(host_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_participant_left',
                            'data': has_entries({
                                'conference_id': adhoc_conference_id,
                                'call_id': participant2_call_id,
                            })})))
            assert_that(participant1_events.accumulate(),
                        has_item(has_entries({
                            'name': 'conference_adhoc_participant_left',
                            'data': has_entries({
                                'conference_id': adhoc_conference_id,
                                'call_id': participant2_call_id,
                            })})))
        until.assert_(bus_events_are_sent, timeout=10)
