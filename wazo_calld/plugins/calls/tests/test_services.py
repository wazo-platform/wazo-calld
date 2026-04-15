# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, patch

from ari.exceptions import ARINotFound
from hamcrest import assert_that, calling, equal_to, is_, raises

from ..exceptions import NoSuchCall
from ..services import CallsService


def _make_local_group_callee_channel(match_uuid):
    channel = Mock()
    channel.json = {
        'name': 'Local/user-uuid@usersharedlines-000001;1',
        'channelvars': {
            'WAZO_LOCAL_CHAN_MATCH_UUID': match_uuid,
        },
    }

    def get_channel_var(variable):
        if variable == 'WAZO_RECORD_GROUP_CALLEE':
            return {'value': '1'}
        return {'value': ''}

    channel.getChannelVar.side_effect = get_channel_var
    return channel


def _make_pjsip_channel(name, match_uuid, state='Up', record_side='callee'):
    channel = Mock()
    channel.json = {
        'name': name,
        'state': state,
        'channelvars': {
            'WAZO_LOCAL_CHAN_MATCH_UUID': match_uuid,
            'WAZO_CALL_RECORD_SIDE': record_side,
        },
    }
    return channel


class TestServices(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.services = CallsService(
            Mock(), Mock(), self.ari, Mock(), Mock(), Mock(), Mock()
        )

        self.example_to_fit: dict = {
            'type': 'ChannelDestroyed',
            'timestamp': '2021-06-15T11:06:46.331-0400',
            'cause': 3,
            'cause_txt': 'No route to destination',
            'channel': {
                'id': '1623769434.135',
                'name': 'PJSIP/HwnelF4k-00000075',
                'state': 'Up',
                'caller': {'name': 'Oxynor', 'number': '9000'},
                'connected': {'name': 'Xelanir', 'number': '9001'},
                'accountcode': '',
                'dialplan': {
                    'context': 'pickup',
                    'exten': 'my_pickup',
                    'priority': 3,
                    'app_name': '',
                    'app_data': '',
                },
                'creationtime': '2021-06-15T11:06' ':45.465-0400',
                'language': 'en_US',
                'channelvars': {
                    'CHANNEL(linkedid)': '1623743605.135',
                    'WAZO_CALL_RECORD_ACTIVE': '',
                    'WAZO_DEREFERENCED_USERUUID': '',
                    'WAZO_ENTRY_CONTEXT': 'default-key-2354-internal',
                    'WAZO_ENTRY_EXTEN': '9001',
                    'WAZO_LINE_ID': '2',
                    'WAZO_SIP_CALL_ID': 'coNsbzfk_Tcq2cffBi9g7Q..',
                    'WAZO_SWITCHBOARD_QUEUE': '',
                    'WAZO_SWITCHBOARD_HOLD': '',
                    'WAZO_TENANT_UUID': '6345gd34-9ac7-4337-818d-d04e606d9f74',
                    'XIVO_BASE_EXTEN': '9001',
                    'XIVO_ON_HOLD': '',
                    'WAZO_USERUUID': '76f7fmfh-a547-4324-a521-e2e04843cfee',
                    'WAZO_LOCAL_CHAN_MATCH_UUID': '',
                    'WAZO_CALL_RECORD_SIDE': 'caller',
                    'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                },
            },
            'asterisk_id': '52:54:00:2a:da:g5',
            'application': 'callcontrol',
        }

    @patch(
        'wazo_calld.plugins.calls.services.CallsService._get_connected_channel_ids_from_helper'
    )
    def test_given_no_chan_variables_when_make_call_from_stasis_event_then_call_has_none_values(
        self, channel_ids
    ):
        channel_ids.return_value = []
        event = self.example_to_fit
        event['channel']['channelvars'] = {}

        call = self.services.channel_destroyed_event(self.ari, event)

        assert_that(call.user_uuid, equal_to(None))
        assert_that(call.dialed_extension, equal_to(None))

    @patch(
        'wazo_calld.plugins.calls.services.CallsService._get_connected_channel_ids_from_helper'
    )
    def test_given_wazo_useruuid_when_make_call_from_stasis_event_then_call_has_useruuid(
        self, channel_ids
    ):
        channel_ids.return_value = []
        event = self.example_to_fit
        event['channel']['channelvars'] = {'WAZO_USERUUID': 'new_useruuid'}

        call = self.services.channel_destroyed_event(self.ari, event)

        assert_that(call.user_uuid, equal_to('new_useruuid'))

    @patch(
        'wazo_calld.plugins.calls.services.CallsService._get_connected_channel_ids_from_helper'
    )
    def test_given_wazo_dereferenced_useruuid_when_make_call_from_stasis_event_then_override_wazo_useruuid(
        self, channel_ids
    ):
        channel_ids.return_value = []
        event = self.example_to_fit
        event['channel']['channelvars'] = {
            'WAZO_USERUUID': 'my-user-uuid',
            'WAZO_DEREFERENCED_USERUUID': 'new-user-uuid',
        }

        call = self.services.channel_destroyed_event(self.ari, event)

        assert_that(call.user_uuid, equal_to('new-user-uuid'))

    @patch(
        'wazo_calld.plugins.calls.services.CallsService._get_connected_channel_ids_from_helper'
    )
    def test_creation_time_from_channel_creation_to_call_on_hungup(self, channel_ids):
        channel_ids.return_value = []
        event = self.example_to_fit
        creation_time = event['channel']['creationtime']
        call = self.services.channel_destroyed_event(self.ari, event)

        assert_that(call.creation_time, equal_to(creation_time))

    @patch(
        'wazo_calld.plugins.calls.services.CallsService._get_connected_channel_ids_from_helper'
    )
    def test_direction_of_call_to_who_is_caller(self, channel_ids):
        channel_ids.return_value = []
        event = self.example_to_fit
        call = self.services.channel_destroyed_event(self.ari, event)

        assert_that(call.is_caller, equal_to(True))

    def test_call_direction(self):
        inbound_channel = 'inbound'
        outbound_channel = 'outbound'
        internal_channel = 'internal'
        unknown_channel = 'unknown'

        direction = self.services._conversation_direction_from_directions

        assert_that(direction([]), equal_to(internal_channel))

        assert_that(direction([internal_channel]), equal_to(internal_channel))
        assert_that(direction([inbound_channel]), equal_to(inbound_channel))
        assert_that(direction([outbound_channel]), equal_to(outbound_channel))

        assert_that(
            direction([inbound_channel, inbound_channel]), equal_to(inbound_channel)
        )
        assert_that(
            direction([inbound_channel, outbound_channel]), equal_to(unknown_channel)
        )
        assert_that(
            direction([inbound_channel, internal_channel]), equal_to(inbound_channel)
        )
        assert_that(
            direction([outbound_channel, inbound_channel]), equal_to(unknown_channel)
        )
        assert_that(
            direction([outbound_channel, outbound_channel]), equal_to(outbound_channel)
        )
        assert_that(
            direction([outbound_channel, internal_channel]), equal_to(outbound_channel)
        )
        assert_that(
            direction([internal_channel, inbound_channel]), equal_to(inbound_channel)
        )
        assert_that(
            direction([internal_channel, outbound_channel]), equal_to(outbound_channel)
        )
        assert_that(
            direction([internal_channel, internal_channel]), equal_to(internal_channel)
        )

        assert_that(
            direction([inbound_channel, inbound_channel, inbound_channel]),
            equal_to(inbound_channel),
        )
        assert_that(
            direction([inbound_channel, outbound_channel, inbound_channel]),
            equal_to(unknown_channel),
        )
        assert_that(
            direction([inbound_channel, internal_channel, internal_channel]),
            equal_to(inbound_channel),
        )
        assert_that(
            direction([outbound_channel, inbound_channel, outbound_channel]),
            equal_to(unknown_channel),
        )
        assert_that(
            direction([outbound_channel, outbound_channel, outbound_channel]),
            equal_to(outbound_channel),
        )
        assert_that(
            direction([outbound_channel, internal_channel, internal_channel]),
            equal_to(outbound_channel),
        )
        assert_that(
            direction([internal_channel, inbound_channel, internal_channel]),
            equal_to(inbound_channel),
        )
        assert_that(
            direction([internal_channel, outbound_channel, internal_channel]),
            equal_to(outbound_channel),
        )
        assert_that(
            direction([internal_channel, internal_channel, internal_channel]),
            equal_to(internal_channel),
        )


def _make_channel_mock(
    channel_id: str,
    name: str,
    channelvars: dict | None = None,
    getvar_side_effect: dict | None = None,
) -> Mock:
    default_vars = {
        'WAZO_LOCAL_CHAN_MATCH_UUID': '',
        'WAZO_CALL_RECORD_SIDE': 'caller',
    }
    if channelvars:
        default_vars.update(channelvars)

    channel = Mock()
    channel.id = channel_id
    channel.json = {'name': name, 'state': 'Up', 'channelvars': default_vars}

    def _getvar(variable=''):
        if getvar_side_effect and variable in getvar_side_effect:
            result = getvar_side_effect[variable]
            if isinstance(result, Exception):
                raise result
            return result
        raise ARINotFound(Mock(), Mock())

    channel.getChannelVar = Mock(side_effect=_getvar)
    return channel


class TestFindChannelToRecord(TestCase):
    def setUp(self) -> None:
        self.ari = Mock()
        self.services = CallsService(
            Mock(), Mock(), self.ari, Mock(), Mock(), Mock(), Mock()
        )

    def test_group_callee_returns_answered_channel(self):
        call_uuid = 'shared-group-call-uuid'
        local_channel = _make_local_group_callee_channel(call_uuid)
        answered_pjsip = _make_pjsip_channel(
            'PJSIP/answered-001', call_uuid, state='Up'
        )

        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [answered_pjsip]

        result = self.services._find_channel_to_record('local-chan-id')

        assert_that(result, equal_to(answered_pjsip))

    def test_group_callee_skips_ringing_channels(self):
        call_uuid = 'shared-group-call-uuid'
        local_channel = _make_local_group_callee_channel(call_uuid)
        ringing_pjsip = _make_pjsip_channel(
            'PJSIP/ringing-001', call_uuid, state='Ring'
        )
        answered_pjsip = _make_pjsip_channel(
            'PJSIP/answered-002', call_uuid, state='Up'
        )

        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [ringing_pjsip, answered_pjsip]

        result = self.services._find_channel_to_record('local-chan-id')

        assert_that(result, equal_to(answered_pjsip))

    def test_group_callee_falls_back_to_local_when_no_channel_is_up(self):
        call_uuid = 'shared-group-call-uuid'
        local_channel = _make_local_group_callee_channel(call_uuid)
        ringing_pjsip_1 = _make_pjsip_channel(
            'PJSIP/ringing-001', call_uuid, state='Ring'
        )
        ringing_pjsip_2 = _make_pjsip_channel(
            'PJSIP/ringing-002', call_uuid, state='Ring'
        )

        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [ringing_pjsip_1, ringing_pjsip_2]

        result = self.services._find_channel_to_record('local-chan-id')

        assert_that(result, equal_to(local_channel))

    def test_channel_not_found_raises_no_such_call(self) -> None:
        self.ari.channels.get.side_effect = ARINotFound(Mock(), Mock())

        assert_that(
            calling(self.services._find_channel_to_record).with_args('missing-id'),
            raises(NoSuchCall),
        )

    def test_non_local_channel_returned_as_is(self) -> None:
        channel = _make_channel_mock('chan-1', 'PJSIP/abcd-00000001')
        self.ari.channels.get.return_value = channel

        result = self.services._find_channel_to_record('chan-1')

        assert_that(result, is_(channel))

    def test_local_side_2_returned_as_is(self) -> None:
        channel = _make_channel_mock('chan-1', 'Local/s@group;2')
        self.ari.channels.get.return_value = channel

        result = self.services._find_channel_to_record('chan-1')

        assert_that(result, is_(channel))

    def test_local_side_1_not_group_nor_queue_returned_as_is(self) -> None:
        channel = _make_channel_mock('chan-1', 'Local/s@some-context;1')
        self.ari.channels.get.return_value = channel

        result = self.services._find_channel_to_record('chan-1')

        assert_that(result, is_(channel))

    def test_local_side_1_group_callee_returns_real_channel(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@group;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid'},
            getvar_side_effect={
                'WAZO_RECORD_GROUP_CALLEE': {'value': '1'},
            },
        )
        real_channel = _make_channel_mock(
            'real-1',
            'PJSIP/abcd-00000001',
            channelvars={
                'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid',
                'WAZO_CALL_RECORD_SIDE': 'callee',
            },
        )
        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [local_channel, real_channel]

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(real_channel))

    def test_local_side_1_queue_callee_returns_real_channel(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@queue;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid'},
            getvar_side_effect={
                'WAZO_RECORD_GROUP_CALLEE': ARINotFound(Mock(), Mock()),
                'WAZO_RECORD_QUEUE_CALLEE': {'value': '1'},
            },
        )
        real_channel = _make_channel_mock(
            'real-1',
            'PJSIP/abcd-00000001',
            channelvars={
                'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid',
                'WAZO_CALL_RECORD_SIDE': 'callee',
            },
        )
        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [real_channel]

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(real_channel))

    def test_local_side_1_agent_callback_returns_real_channel(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@agentcallback;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid'},
        )
        real_channel = _make_channel_mock(
            'real-1',
            'PJSIP/abcd-00000001',
            channelvars={
                'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid',
                'WAZO_CALL_RECORD_SIDE': 'callee',
            },
        )
        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [real_channel]

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(real_channel))

    def test_local_side_1_group_callee_no_match_uuid_returns_local(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@group;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': ''},
            getvar_side_effect={
                'WAZO_RECORD_GROUP_CALLEE': {'value': '1'},
            },
        )
        self.ari.channels.get.return_value = local_channel

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(local_channel))

    def test_local_side_1_group_callee_no_matching_channel_returns_local(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@group;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid'},
            getvar_side_effect={
                'WAZO_RECORD_GROUP_CALLEE': {'value': '1'},
            },
        )
        unrelated_channel = _make_channel_mock(
            'other-1',
            'PJSIP/xyz-00000002',
            channelvars={
                'WAZO_LOCAL_CHAN_MATCH_UUID': 'different-uuid',
                'WAZO_CALL_RECORD_SIDE': 'callee',
            },
        )
        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [local_channel, unrelated_channel]

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(local_channel))

    def test_skips_local_channels_when_searching(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@group;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid'},
            getvar_side_effect={
                'WAZO_RECORD_GROUP_CALLEE': {'value': '1'},
            },
        )
        other_local = _make_channel_mock(
            'local-2',
            'Local/s@other;2',
            channelvars={
                'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid',
                'WAZO_CALL_RECORD_SIDE': 'callee',
            },
        )
        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [local_channel, other_local]

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(local_channel))

    def test_skips_caller_side_channels_when_searching(self) -> None:
        local_channel = _make_channel_mock(
            'local-1',
            'Local/s@group;1',
            channelvars={'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid'},
            getvar_side_effect={
                'WAZO_RECORD_GROUP_CALLEE': {'value': '1'},
            },
        )
        caller_channel = _make_channel_mock(
            'caller-1',
            'PJSIP/abcd-00000001',
            channelvars={
                'WAZO_LOCAL_CHAN_MATCH_UUID': 'match-uuid',
                'WAZO_CALL_RECORD_SIDE': 'caller',
            },
        )
        self.ari.channels.get.return_value = local_channel
        self.ari.channels.list.return_value = [caller_channel]

        result = self.services._find_channel_to_record('local-1')

        assert_that(result, is_(local_channel))


class TestRecordingUsesFoundChannel(TestCase):
    """Verify that record_start/stop/pause/resume use the channel returned by
    _find_channel_to_record (channel.id) rather than the original call_id for
    AMI and ARI operations."""

    def setUp(self) -> None:
        self.ari = Mock()
        self.amid = Mock()
        self.notifier = Mock()
        self.services = CallsService(
            self.amid, Mock(), self.ari, Mock(), Mock(), Mock(), self.notifier
        )

        self.call_id = 'original-call-id'
        self.found_channel_id = 'found-channel-id'

        self.found_channel = _make_channel_mock(
            self.found_channel_id,
            'PJSIP/abcd-00000001',
            channelvars={
                'WAZO_CALL_RECORD_ACTIVE': '0',
                'WAZO_TENANT_UUID': 'tenant-1',
                'WAZO_USERUUID': 'user-1',
                'WAZO_RECORDING_UUID': 'rec-uuid',
                'WAZO_RECORDING_PAUSED': '0',
                'WAZO_QUEUENAME': '',
                'WAZO_GROUPNAME': '',
                'WAZO_CALL_RECORD_SIDE': 'caller',
                'WAZO_QUEUE_DTMF_RECORD_TOGGLE_ENABLED': '0',
                'WAZO_GROUP_DTMF_RECORD_TOGGLE_ENABLED': '0',
                'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1',
                'WAZO_RECORD_GROUP_CALLEE': '0',
                'WAZO_RECORD_QUEUE_CALLEE': '0',
            },
        )

        # _find_channel_to_record returns a different channel than call_id
        find_patcher = patch.object(
            self.services, '_find_channel_to_record', return_value=self.found_channel
        )
        self.mock_find = find_patcher.start()
        self.addCleanup(find_patcher.stop)

        # _is_automated_recording fetches channel by id from ARI
        self.ari.channels.get.return_value = self.found_channel

        # Bypass tenant check
        tenant_patcher = patch(
            'wazo_calld.plugins.calls.services.Channel',
        )
        mock_channel_cls = tenant_patcher.start()
        mock_channel_cls.return_value.tenant_uuid.return_value = None
        self.addCleanup(tenant_patcher.stop)

        # make_call_from_channel is used in stop/pause/resume
        make_call_patcher = patch.object(
            self.services, 'make_call_from_channel', return_value=Mock()
        )
        make_call_patcher.start()
        self.addCleanup(make_call_patcher.stop)

    @patch('wazo_calld.plugins.calls.services.ami')
    @patch('wazo_calld.plugins.calls.services.set_channel_id_var_sync')
    def test_record_start_uses_found_channel_id(
        self, mock_set_var: Mock, mock_ami: Mock
    ) -> None:
        self.services.record_start(None, self.call_id)

        mock_set_var.assert_called_once()
        assert_that(mock_set_var.call_args[0][1], equal_to(self.found_channel_id))
        mock_ami.record_start.assert_called_once()
        assert_that(
            mock_ami.record_start.call_args[0][1], equal_to(self.found_channel_id)
        )
        mock_ami.play_beep.assert_called_once()
        assert_that(mock_ami.play_beep.call_args[0][1], equal_to(self.found_channel_id))

    @patch('wazo_calld.plugins.calls.services.ami')
    def test_record_stop_uses_found_channel_id(self, mock_ami: Mock) -> None:
        self.found_channel.json['channelvars']['WAZO_CALL_RECORD_ACTIVE'] = '1'

        self.services.record_stop(None, self.call_id)

        mock_ami.record_stop.assert_called_once()
        assert_that(
            mock_ami.record_stop.call_args[0][1], equal_to(self.found_channel_id)
        )
        mock_ami.play_beep.assert_called_once()
        assert_that(mock_ami.play_beep.call_args[0][1], equal_to(self.found_channel_id))

    @patch('wazo_calld.plugins.calls.services.ami')
    @patch('wazo_calld.plugins.calls.services.set_channel_id_var_sync')
    def test_record_pause_uses_found_channel_id(
        self, mock_set_var: Mock, mock_ami: Mock
    ) -> None:
        self.found_channel.json['channelvars']['WAZO_CALL_RECORD_ACTIVE'] = '1'

        self.services.record_pause(None, self.call_id)

        mock_set_var.assert_called_once()
        assert_that(mock_set_var.call_args[0][1], equal_to(self.found_channel_id))
        mock_ami.record_stop.assert_called_once()
        assert_that(
            mock_ami.record_stop.call_args[0][1], equal_to(self.found_channel_id)
        )
        mock_ami.play_beep.assert_called_once()
        assert_that(mock_ami.play_beep.call_args[0][1], equal_to(self.found_channel_id))

    @patch('wazo_calld.plugins.calls.services.ami')
    @patch('wazo_calld.plugins.calls.services.set_channel_id_var_sync')
    def test_record_resume_uses_found_channel_id(
        self, mock_set_var: Mock, mock_ami: Mock
    ) -> None:
        self.found_channel.json['channelvars']['WAZO_CALL_RECORD_ACTIVE'] = '1'
        self.found_channel.json['channelvars']['WAZO_RECORDING_PAUSED'] = '1'

        self.services.record_resume(None, self.call_id)

        mock_set_var.assert_called_once()
        assert_that(mock_set_var.call_args[0][1], equal_to(self.found_channel_id))
        mock_ami.record_resume.assert_called_once()
        assert_that(
            mock_ami.record_resume.call_args[0][1], equal_to(self.found_channel_id)
        )
        mock_ami.play_beep.assert_called_once()
        assert_that(mock_ami.play_beep.call_args[0][1], equal_to(self.found_channel_id))
