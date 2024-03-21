# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from functools import wraps
from typing import TYPE_CHECKING, Callable, TypedDict, cast
from uuid import uuid4

from ari.exceptions import ARINotFound
from hamcrest import (
    assert_that,
    calling,
    empty,
    equal_to,
    has_entries,
    has_item,
    has_properties,
    not_,
)
from typing_extensions import NotRequired, Required, Unpack
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.confd import MockParkinglot
from .helpers.constants import ENDPOINT_AUTOANSWER, VALID_TENANT
from .helpers.hamcrest_ import HamcrestARIBridge, HamcrestARIChannel
from .helpers.real_asterisk import RealAsterisk, RealAsteriskIntegrationTest

if TYPE_CHECKING:
    from .helpers.schemas import ParkingLotSchema


class ParkingLotArgs(TypedDict, total=False):
    id: Required[int]
    tenant_uuid: NotRequired[str]
    name: NotRequired[str]
    extension: NotRequired[int]
    slots_start: NotRequired[str]
    slots_end: NotRequired[str]
    timeout: NotRequired[int]


# NOTE: Parkings must be defined in `/etc/asterisk/res_parking.conf`
PARKINGLOT_1: ParkingLotArgs = {
    'id': 1,
    'tenant_uuid': VALID_TENANT,
    'name': 'First Parking',
    'extension': 500,
    'slots_start': '501',
    'slots_end': '510',
    'timeout': 5,
}
PARKINGLOT_2: ParkingLotArgs = {
    'id': 2,
    'tenant_uuid': 'b93892f0-5300-4682-aede-3104b449ba69',
    'name': 'Second Parking',
    'extension': 600,
    'slots_start': '601',
    'slots_end': '602',
    'timeout': 0,
}


class Fixture:
    @staticmethod
    def parking_lot(**parking_lot: Unpack[ParkingLotArgs]) -> Callable[..., None]:
        def decorator(decorated: Callable):
            @wraps(decorated)
            def wrapper(test: RealAsteriskIntegrationTest, *args, **kwargs):
                parkinglot = MockParkinglot(**cast(ParkingLotArgs, parking_lot))

                test.confd.set_parkinglots(parkinglot)
                test.bus.send_confd_parking_created(parking_lot['id'])

                args = args + (parkinglot.to_dict(),)
                try:
                    return decorated(test, *args, **kwargs)
                finally:
                    # must send bus message to clear parking cache
                    test.bus.send_confd_parking_deleted(parking_lot['id'])

            return wrapper

        return decorator


def random_uuid() -> str:
    return str(uuid4())


class BaseParkingTest(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.confd.reset()
        self.b = HamcrestARIBridge(self.ari)
        self.c = HamcrestARIChannel(self.ari)
        self.real_asterisk = RealAsterisk(self.ari, self.calld_client)

    def tearDown(self):
        super().tearDown()
        for bridge in self.ari.bridges.list():
            for channel_id in bridge.json['channels']:
                try:
                    self.ari.channels.get(channelId=channel_id).hangup()
                except ARINotFound:
                    pass

    def given_parked_call(
        self,
        parking_extension: str,
        *,
        tenant_uuid: str | None = VALID_TENANT,
        user_uuid: str | None = None,
    ) -> Generator[str, None, None]:
        variables = {}
        if tenant_uuid:
            variables['WAZO_TENANT_UUID'] = tenant_uuid
        if user_uuid:
            variables['WAZO_USERUUID'] = user_uuid

        channel = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='parkings',
            extension=parking_extension,
            variables={'variables': variables},
        )

        def is_parked(channel) -> None:
            assert_that(channel.id, self.c.is_in_bridge(), 'Channel is not parked')

        until.assert_(is_parked, channel, timeout=3)
        return channel.id


class TestParkings(BaseParkingTest):
    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_get_parking(self, parking: ParkingLotSchema):
        parking_extension = parking['extensions'][0]['exten']

        result = self.calld_client.parking_lots.get(parking['id'])
        assert_that(result['calls'], empty())

        call_id = self.given_parked_call(parking_extension)
        response = self.calld_client.parking_lots.get(parking['id'])

        assert_that(
            response,
            has_entries(
                calls=has_item(
                    has_entries(call_id=call_id),
                )
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_get_parking_no_confd(self, parking: ParkingLotSchema):
        with self.confd_stopped():
            assert_that(
                calling(self.calld_client.parking_lots.get).with_args(parking['id']),
                raises(CalldError).matching(
                    has_properties(status_code=503, error_id='wazo-confd-unreachable')
                ),
            )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_get_parking_no_amid(self, parking: ParkingLotSchema):
        with self.amid_stopped():
            assert_that(
                calling(self.calld_client.parking_lots.get).with_args(parking['id']),
                raises(CalldError).matching(
                    has_properties(status_code=503, error_id='wazo-amid-error')
                ),
            )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_get_parking_wrong_parking_id(self, _: ParkingLotSchema):
        assert_that(
            calling(self.calld_client.parking_lots.get).with_args(0),
            raises(CalldError).matching(
                has_properties(status_code=404, error_id='no-such-parking')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_get_wrong_tenant_uuid(self, parking: ParkingLotSchema):
        calld = self.make_user_calld(
            user_uuid=random_uuid(), tenant_uuid='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1'
        )

        assert_that(
            calling(calld.parking_lots.get).with_args(parking['id']),
            raises(CalldError).matching(
                has_properties(status_code=404, error_id='no-such-parking')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_park_updates_call_object(self, parking: ParkingLotSchema) -> None:
        caller, callee = self.real_asterisk.given_bridged_call_not_stasis()
        parked_event = self.bus.accumulator(headers={'name': 'call_parked'})

        response = self.calld_client.calls.get_call(caller)
        assert_that(response, has_entries(call_id=caller, parked=False))

        def get_parked_event():
            try:
                return parked_event.pop(with_headers=False)
            except IndexError:
                return False

        self.calld_client.calls.park(caller, parking['id'])
        assert_that(
            until.true(get_parked_event, timeout=3),
            has_entries(data=has_entries(call_id=caller)),
        )

        response = self.calld_client.calls.get_call(caller)
        assert_that(response, has_entries(call_id=caller, parked=True))

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_park_call(self, parking: ParkingLotSchema) -> None:
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})

        def get_parked_call_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()
        response = self.calld_client.calls.park(caller, parking['id'], timeout=0)

        parked_event = until.true(get_parked_call_event, timeout=3)
        assert_that(
            parked_event,
            has_entries(
                name='call_parked',
                data=has_entries(
                    call_id=caller, slot=response['slot'], parking_id=parking['id']
                ),
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_2)
    def test_park_error_when_parking_is_in_another_tenant(
        self, parking: ParkingLotSchema
    ) -> None:
        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.park).with_args(caller, parking['id']),
            raises(CalldError).matching(
                has_properties(status_code=404, error_id='no-such-parking')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_park_error_when_user_is_in_another_tenant(
        self, parking: ParkingLotSchema
    ) -> None:
        user_uuid = random_uuid()
        other_tenant_uuid = random_uuid()
        caller, _ = self.real_asterisk.given_bridged_call_not_stasis(
            caller_uuid=user_uuid,
            caller_variables={'WAZO_TENANT_UUID': other_tenant_uuid},
        )

        assert_that(
            calling(self.calld_client.calls.park).with_args(caller, parking['id']),
            raises(CalldError).matching(
                has_properties(status_code=404, error_id="no-such-call")
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_error_when_trying_to_park_before_call_connected(
        self, parking: ParkingLotSchema
    ) -> None:
        caller, callee = self.real_asterisk.given_ringing_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.park).with_args(caller, parking['id']),
            raises(CalldError).matching(
                has_properties(status_code=400, error_id='cannot-park-call')
            ),
        )

        assert_that(
            calling(self.calld_client.calls.park).with_args(callee, parking['id']),
            raises(CalldError).matching(
                has_properties(status_code=400, error_id='cannot-park-call')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_503_when_parking_is_full(self, parking: ParkingLotSchema) -> None:
        for _ in range(10):
            self.given_parked_call(parking['extensions'][0]['exten'])

        response = self.calld_client.parking_lots.get(parking['id'])
        assert_that(response, has_entries('slots_remaining', equal_to(0)))

        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.park).with_args(caller, parking['id']),
            raises(CalldError).matching(
                has_properties(status_code=503, error_id='parking-full')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_park_call_with_preferred_slot(self, parking: ParkingLotSchema) -> None:
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})

        def get_parked_call_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()
        response = self.calld_client.calls.park(
            caller, parking['id'], preferred_slot='505'
        )

        assert_that(response, has_entries(slot='505'))

        parked_event = until.true(get_parked_call_event, timeout=3)
        assert_that(
            parked_event,
            has_entries(
                name='call_parked',
                data=has_entries(call_id=caller, parking_id=parking['id'], slot='505'),
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_park_call_with_preferred_slot_already_taken_takes_next_slot(
        self, parking: ParkingLotSchema
    ) -> None:
        self.given_parked_call(parking['extensions'][0]['exten'])
        response = self.calld_client.parking_lots.get(parking['id'])
        parking_slot = response['calls'][0]['slot']
        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()

        response = self.calld_client.calls.park(
            caller, parking['id'], preferred_slot=parking_slot
        )

        assert_that(response, not_(has_entries(slot=parking_slot)))

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_park_while_already_parked_with_same_preferred_slot_keeps_same_slot(
        self, parking: ParkingLotSchema
    ) -> None:
        caller = self.given_parked_call(parking['extensions'][0]['exten'])
        parking_slot = self.calld_client.parking_lots.get(parking['id'])['calls'][0][
            'slot'
        ]

        response = self.calld_client.calls.park(
            caller, parking['id'], preferred_slot=parking_slot
        )
        assert_that(response, has_entries(slot=parking_slot))

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_park_while_already_parked_reparks_in_another_slot(
        self, parking: ParkingLotSchema
    ) -> None:
        caller = self.given_parked_call(parking['extensions'][0]['exten'])
        parking_slot = self.calld_client.parking_lots.get(parking['id'])['calls'][0][
            'slot'
        ]

        response = self.calld_client.calls.park(caller, parking['id'])
        assert_that(response, not_(has_entries(slot=parking_slot)))

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_park_timeout_callback(self, parking: ParkingLotSchema) -> None:
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})
        timeout_events = self.bus.accumulator(headers={'name': 'parked_call_timed_out'})

        def call_is_parked(call_id):
            assert_that(
                parked_events.accumulate(with_headers=False),
                has_item(
                    has_entries(
                        name='call_parked',
                        tenant_uuid=VALID_TENANT,
                        data=has_entries(call_id=call_id, parking_id=parking['id']),
                    )
                ),
            )

        def parked_call_timed_out():
            assert_that(
                timeout_events.accumulate(),
                has_item(
                    has_entries(
                        name='parked_call_timed_out',
                        data=has_entries(call_id=caller, parking_id=parking['id']),
                    )
                ),
            )

        def call_ended(call_id):
            assert_that(
                call_ended_events.accumulate(with_headers=False),
                has_item(
                    has_entries(
                        name='call_ended',
                        data=has_entries(call_id=call_id),
                    )
                ),
            )

        def call_created():
            assert_that(
                call_created_events.accumulate(with_headers=False),
                has_item(
                    has_entries(
                        name='call_created',
                        data=has_entries(status='Ringing'),
                    )
                ),
            )

        caller, callee = self.real_asterisk.given_bridged_call_not_stasis()
        self.calld_client.calls.park(caller, parking['id'], timeout=1)

        call_ended_events = self.bus.accumulator(headers={'name': 'call_ended'})
        call_created_events = self.bus.accumulator(headers={'name': 'call_created'})

        until.assert_(call_is_parked, caller, timeout=3)
        until.assert_(call_ended, callee, timeout=3)
        until.assert_(parked_call_timed_out, timeout=3)
        until.assert_(call_created, timeout=3)

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_parked_hangup_event(self, parking: ParkingLotSchema) -> None:
        caller, callee = self.real_asterisk.given_bridged_call_not_stasis()
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})
        ended_events = self.bus.accumulator(headers={'name': 'call_ended'})
        hangup_events = self.bus.accumulator(headers={'name': 'parked_call_hungup'})

        def call_is_parked():
            assert_that(
                parked_events.accumulate(with_headers=False),
                has_item(has_entries(data=has_entries(call_id=caller))),
            )

        def callee_call_ended():
            assert_that(
                ended_events.accumulate(with_headers=False),
                has_item(has_entries(data=has_entries(call_id=callee))),
            )

        def parked_call_is_hungup():
            assert_that(
                hangup_events.accumulate(with_headers=False),
                has_item(has_entries(data=has_entries(call_id=caller))),
            )

        self.calld_client.calls.park(caller, parking['id'], timeout=10)

        until.assert_(call_is_parked, timeout=3)
        until.assert_(callee_call_ended, timeout=3)

        self.ari.channels.get(channelId=caller).hangup()

        until.assert_(parked_call_is_hungup, timeout=10)

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_park_timeout_values(self, parking: ParkingLotSchema) -> None:
        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})

        def get_parked_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        now = datetime.now(timezone.utc).replace(microsecond=0)
        response = self.calld_client.calls.park(caller, parking['id'], timeout=7)

        timeout_at = datetime.fromisoformat(response['timeout_at'])
        assert (timeout_at - now).total_seconds() >= 7

        event = until.true(get_parked_event, timeout=3)
        timeout_at = datetime.fromisoformat(event['data']['timeout_at'])

        assert (timeout_at - now).total_seconds() >= 7

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_call_park_timeout_infinite(self, parking: ParkingLotSchema) -> None:
        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})

        def get_parked_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        response = self.calld_client.calls.park(caller, parking['id'], timeout=0)
        event = until.true(get_parked_event, timeout=3)

        assert response['timeout_at'] is None
        assert event['data']['timeout_at'] is None

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_reparking_call_updates_timeout(self, parking: ParkingLotSchema) -> None:
        caller, _ = self.real_asterisk.given_bridged_call_not_stasis()

        def get_parked_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.calld_client.calls.park(caller, parking['id'], timeout=5)

        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})
        response = self.calld_client.calls.park(caller, parking['id'], timeout=12345)

        timeout_at = datetime.fromisoformat(response['timeout_at'])
        assert (timeout_at - now).total_seconds() >= 12345

        event = until.true(get_parked_event, timeout=3)
        timeout_at = datetime.fromisoformat(event['data']['timeout_at'])
        assert (timeout_at - now).total_seconds() >= 12345

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_park_stasis(self, parking: ParkingLotSchema) -> None:
        caller, _ = self.real_asterisk.given_bridged_call_stasis()
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})

        def get_parked_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        self.calld_client.calls.park(caller, parking['id'], preferred_slot='510')

        event = until.true(get_parked_event, timeout=3)
        assert_that(
            event,
            has_entries(
                data=has_entries(call_id=caller, parking_id=parking['id'], slot='510')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_user_call_park(self, parking: ParkingLotSchema) -> None:
        user_uuid = random_uuid()
        calld = self.make_user_calld(user_uuid)

        caller, callee = self.real_asterisk.given_bridged_call_not_stasis(
            caller_uuid=user_uuid
        )
        parked_events = self.bus.accumulator(headers={'name': 'call_parked'})

        def get_call_parked_event():
            try:
                return parked_events.pop(with_headers=False)
            except IndexError:
                return False

        calld.calls.park_collocutor_from_user(caller, parking['id'])

        event = until.true(get_call_parked_event, timeout=3)

        assert_that(event, has_entries(data=has_entries(call_id=callee)))

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_user_call_park_invalid_call(self, parking: ParkingLotSchema):
        user_uuid = random_uuid()
        calld = self.make_user_calld(user_uuid)

        caller = self.given_parked_call(
            parking['extensions'][0]['exten'], user_uuid=user_uuid
        )

        assert_that(
            calling(calld.calls.park_collocutor_from_user).with_args(
                caller, parking['id']
            ),
            raises(CalldError).matching(
                has_properties(status_code=400, error_id='cannot-park-call')
            ),
        )

    @Fixture.parking_lot(**PARKINGLOT_1)
    def test_user_call_park_permissions(self, parking: ParkingLotSchema) -> None:
        user_uuid = random_uuid()
        some_other_user_uuid = random_uuid()
        calld = self.make_user_calld(user_uuid)

        not_user_call, user_call = self.real_asterisk.given_bridged_call_not_stasis(
            caller_uuid=some_other_user_uuid,
            callee_uuid=user_uuid,
        )

        assert_that(
            calling(calld.calls.park_collocutor_from_user).with_args(
                not_user_call, parking['id']
            ),
            raises(CalldError).matching(
                has_properties(status_code=403, error_id='user-permission-denied')
            ),
        )

        assert_that(
            calling(calld.calls.park_collocutor_from_user).with_args(
                user_call, parking['id']
            ),
            not_(raises(CalldError)),
        )
