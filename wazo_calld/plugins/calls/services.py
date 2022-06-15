# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import logging
import uuid

from ari.exceptions import ARINotFound
from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME
from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.ari_ import AUTO_ANSWER_VARIABLES, Channel, set_channel_var_sync, set_channel_id_var_sync
from wazo_calld.plugin_helpers.confd import User
from wazo_calld.plugin_helpers.exceptions import (
    InvalidExtension,
    UserPermissionDenied,
)
from xivo.asterisk.protocol_interface import protocol_interface_from_channel

from .call import Call
from .exceptions import CallConnectError
from .exceptions import CallCreationError
from .exceptions import NoSuchCall
from .state_persistor import ReadOnlyStatePersistor
from .dial_echo import DialEchoTimeout

logger = logging.getLogger(__name__)

CALL_RECORDING_FILENAME_TEMPLATE = '/var/lib/wazo/sounds/tenants/{tenant_uuid}/monitor/{recording_uuid}.wav'
LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo


class CallsService:

    def __init__(self, amid_client, ari_config, ari, confd_client, dial_echo_manager, phoned_client, notifier):
        self._ami = amid_client
        self._ari_config = ari_config
        self._ari = ari
        self._confd = confd_client
        self._dial_echo_manager = dial_echo_manager
        self._phoned_client = phoned_client
        self._notifier = notifier
        self._state_persistor = ReadOnlyStatePersistor(self._ari)

    def list_calls(self, application_filter=None, application_instance_filter=None):
        channels = self._ari.channels.list()

        if application_filter:
            try:
                channel_ids = self._ari.applications.get(applicationName=application_filter)['channel_ids']
            except ARINotFound:
                channel_ids = []

            if '__AST_CHANNEL_ALL_TOPIC' not in channel_ids:
                channels = [channel for channel in channels if channel.id in channel_ids]

            if application_instance_filter:
                app_instance_channels = []
                for channel in channels:
                    try:
                        channel_cache_entry = self._state_persistor.get(channel.id)
                    except KeyError:
                        continue
                    if (channel_cache_entry.app == application_filter
                       and channel_cache_entry.app_instance == application_instance_filter):
                        app_instance_channels.append(channel)
                channels = app_instance_channels

        return [self.make_call_from_channel(self._ari, channel) for channel in channels]

    def list_calls_user(self, user_uuid, application_filter=None, application_instance_filter=None):
        calls = self.list_calls(application_filter, application_instance_filter)
        return [call for call in calls if call.user_uuid == user_uuid and not Channel(call.id_, self._ari).is_local()]

    def originate(self, request):
        requested_context = request['destination']['context']
        requested_extension = request['destination']['extension']
        requested_priority = request['destination']['priority']

        if not ami.extension_exists(self._ami, requested_context, requested_extension, requested_priority):
            # Context does not exist in the dialplan
            raise InvalidExtension(requested_context, requested_extension)

        source_user = request['source']['user']
        variables = request.get('variables', {})
        dial_echo_request_id = None
        user = User(source_user, self._confd)

        if request['source']['from_mobile']:
            source_mobile = user.mobile_phone_number()
            if not source_mobile:
                raise CallCreationError('User has no mobile phone number', details={'user': source_user})
            source_context = user.main_line().context()

            if not ami.extension_exists(self._ami, source_context, source_mobile, priority=1):
                details = {'user': source_user,
                           'mobile_exten': source_mobile,
                           'mobile_context': source_context}
                raise CallCreationError('User has invalid mobile phone number', details=details)

            endpoint = 'local/s@wazo-originate-mobile-leg1/n'
            context_name, extension, priority = 'wazo-originate-mobile-leg2', 's', 1

            variables.setdefault('_XIVO_USERUUID', source_user)
            variables.setdefault('_WAZO_TENANT_UUID', user.tenant_uuid)
            variables.setdefault('WAZO_DEREFERENCED_USERUUID', source_user)
            variables.setdefault('WAZO_ORIGINATE_MOBILE_PRIORITY', '1')
            variables.setdefault('WAZO_ORIGINATE_MOBILE_EXTENSION', source_mobile)
            variables.setdefault('WAZO_ORIGINATE_MOBILE_CONTEXT', source_context)
            variables.setdefault('XIVO_FIX_CALLERID', '1')
            variables.setdefault('XIVO_ORIGINAL_CALLER_ID', '"{exten}" <{exten}>'.format(exten=requested_extension))
            variables.setdefault('WAZO_ORIGINATE_DESTINATION_PRIORITY', str(requested_priority))
            variables.setdefault('WAZO_ORIGINATE_DESTINATION_EXTENSION', requested_extension)
            variables.setdefault('WAZO_ORIGINATE_DESTINATION_CONTEXT', requested_context)
            variables.setdefault('WAZO_ORIGINATE_DESTINATION_CALLERID_ALL', '"{exten}" <{exten}>'.format(exten=source_mobile))
            dial_echo_request_id = self._dial_echo_manager.new_dial_echo_request()
            variables.setdefault('_WAZO_DIAL_ECHO_REQUEST_ID', dial_echo_request_id)

            channel = self._ari.channels.originate(endpoint=endpoint,
                                                   extension=extension,
                                                   context=context_name,
                                                   priority=priority,
                                                   variables={'variables': variables})
            try:
                channel_id = self._dial_echo_manager.wait(dial_echo_request_id, timeout=5)
            except DialEchoTimeout:
                details = {
                    'mobile_extension': source_mobile,
                    'mobile_context': source_context,
                }
                raise CallCreationError('Could not dial mobile number', details=details)
            channel = self._ari.channels.get(channelId=channel_id)

        else:
            if 'line_id' in request['source']:
                endpoint = user.line(request['source']['line_id']).interface()
            elif request['source']['all_lines']:
                endpoint = "local/%s@usersharedlines" % (source_user,)
            else:
                endpoint = user.main_line().interface()

            context_name, extension, priority = requested_context, requested_extension, requested_priority

            if request['source']['auto_answer']:
                variables.update(AUTO_ANSWER_VARIABLES)

            variables.setdefault('XIVO_FIX_CALLERID', '1')
            variables.setdefault('WAZO_USERUUID', source_user)
            variables.setdefault('_WAZO_TENANT_UUID', user.tenant_uuid)
            variables.setdefault('CONNECTEDLINE(name)', extension)
            variables.setdefault('CONNECTEDLINE(num)', '' if extension.startswith('#') else extension)
            variables.setdefault('CALLERID(name)', extension)
            variables.setdefault('CALLERID(num)', extension)
            variables.setdefault('WAZO_CHANNEL_DIRECTION', 'to-wazo')

            channel = self._ari.channels.originate(endpoint=endpoint,
                                                   extension=extension,
                                                   context=context_name,
                                                   priority=priority,
                                                   variables={'variables': variables})

        call = self.make_call_from_channel(self._ari, channel)
        call.dialed_extension = request['destination']['extension']
        return call

    def originate_user(self, request, user_uuid):
        if 'line_id' in request and not request['from_mobile']:
            context = User(user_uuid, self._confd).line(request['line_id']).context()
        else:
            context = User(user_uuid, self._confd).main_line().context()

        new_request = {
            'destination': {'context': context,
                            'extension': request['extension'],
                            'priority': 1},
            'source': {'user': user_uuid,
                       'from_mobile': request['from_mobile'],
                       'all_lines': request['all_lines']},
            'variables': request['variables']
        }
        if 'line_id' in request:
            new_request['source']['line_id'] = request['line_id']
        if 'auto_answer_caller' in request:
            new_request['source']['auto_answer'] = request['auto_answer_caller']
        return self.originate(new_request)

    def get(self, call_id):
        channel_id = call_id
        try:
            channel = self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            raise NoSuchCall(channel_id)

        return self.make_call_from_channel(self._ari, channel)

    def hangup(self, call_id):
        channel_id = call_id
        try:
            self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            raise NoSuchCall(channel_id)

        self._ari.channels.hangup(channelId=channel_id)

    def mute(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
            set_channel_var_sync(channel, 'WAZO_CALL_MUTED', '1', bypass_stasis=True)
        except ARINotFound:
            raise NoSuchCall(call_id)

        ami.mute(self._ami, call_id)

        # NOTE(fblackburn): asterisk should send back an event
        # instead of falsy pretend that channel is muted
        call = self.make_call_from_channel(self._ari, channel)
        self._notifier.call_updated(call)

    def unmute(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
            set_channel_var_sync(channel, 'WAZO_CALL_MUTED', '', bypass_stasis=True)
        except ARINotFound:
            raise NoSuchCall(call_id)

        ami.unmute(self._ami, call_id)

        # NOTE(fblackburn): asterisk should send back an event
        # instead of falsy pretend that channel is unmuted
        call = self.make_call_from_channel(self._ari, channel)
        self._notifier.call_updated(call)

    def mute_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.mute(call_id)

    def unmute_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.unmute(call_id)

    def hangup_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self._ari.channels.hangup(channelId=call_id)

    def connect_user(self, call_id, user_uuid):
        channel_id = call_id
        endpoint = User(user_uuid, self._confd).main_line().interface()

        try:
            channel = self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            raise NoSuchCall(channel_id)

        try:
            app_instance = self._state_persistor.get(channel_id).app_instance
        except KeyError:
            raise CallConnectError(call_id)

        new_channel = self._ari.channels.originate(endpoint=endpoint,
                                                   app=DEFAULT_APPLICATION_NAME,
                                                   appArgs=[app_instance, 'dialed_from', channel_id],
                                                   originator=call_id)

        # if the caller hangs up, we cancel our originate
        originate_canceller = channel.on_event('StasisEnd', lambda _, __: self.hangup(new_channel.id))
        # if the callee accepts, we don't have to cancel anything
        new_channel.on_event('StasisStart', lambda _, __: originate_canceller.close())
        # if the callee refuses, leave the caller as it is

        return new_channel.id

    def make_call_from_channel(self, ari, channel):
        channel_variables = channel.json.get('channelvars', {})
        channel_helper = Channel(channel.id, ari)
        call = Call(channel.id)
        call.conversation_id = channel_helper.conversation_id()
        call.creation_time = channel.json['creationtime']
        call.answer_time = channel_variables.get('WAZO_ANSWER_TIME') or None
        call.status = channel.json['state']
        call.caller_id_name = channel.json['caller']['name']
        call.caller_id_number = channel.json['caller']['number']
        call.peer_caller_id_name = channel.json['connected']['name']
        call.peer_caller_id_number = channel.json['connected']['number']
        call.user_uuid = channel_helper.user()
        call.tenant_uuid = channel_helper.tenant_uuid()
        call.on_hold = channel_helper.on_hold()
        call.muted = channel_helper.muted()
        call.record_state = 'active' if channel_variables.get('WAZO_CALL_RECORD_ACTIVE') == '1' else 'inactive'
        call.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]
        call.talking_to = {connected_channel.id: connected_channel.user()
                           for connected_channel in channel_helper.connected_channels()}
        call.is_caller = channel_helper.is_caller()
        call.is_video = channel_variables.get('CHANNEL(videonativeformat)') != '(nothing)'
        call.dialed_extension = channel_helper.dialed_extension()
        call.sip_call_id = channel_helper.sip_call_id()
        call.line_id = channel_helper.line_id()
        connected_channels = channel_helper.connected_channels()
        call.direction = channel_variables.get('WAZO_CONVERSATION_DIRECTION') or (
            self.conversation_direction_from_channels([channel, *connected_channels])
        ) or 'unknown'

        return call

    @staticmethod
    def channel_destroyed_event(event):
        channel = event['channel']
        channel_id = channel.get('id')
        channel_variables = event['channel']['channelvars']
        conversation_id = channel_variables.get('CHANNEL(linkedid)')
        connected = channel.get('connected')
        caller = channel.get('caller')
        call = Call(channel_id)
        call.conversation_id = conversation_id
        call.status = event['channel']['state']
        call.caller_id_name = connected.get('name')
        call.caller_id_number = connected.get('number')
        call.peer_caller_id_name = caller.get('name')
        call.peer_caller_id_number = caller.get('number')
        call.user_uuid = channel_variables.get('WAZO_DEREFERENCED_USERUUID') or channel_variables.get('XIVO_USERUUID') or None
        call.tenant_uuid = channel_variables.get('WAZO_TENANT_UUID') or None
        call.dialed_extension = channel_variables.get('WAZO_ENTRY_EXTEN') or None
        call.bridges = []
        call.talking_to = {}
        call.sip_call_id = channel_variables.get('WAZO_SIP_CALL_ID')
        call.line_id = channel_variables.get('WAZO_LINE_ID') or None
        call.creation_time = channel.get('creationtime')
        call.answer_time = channel_variables.get('WAZO_ANSWER_TIME') or None
        call.hangup_time = datetime.datetime.now(LOCAL_TIMEZONE).isoformat()
        call.is_video = channel_variables.get('CHANNEL(videonativeformat)') != '(nothing)'
        direction = channel_variables.get('WAZO_CHANNEL_DIRECTION')
        call.is_caller = True if direction == 'to-wazo' else False
        call.direction = channel_variables.get('WAZO_CONVERSATION_DIRECTION') or 'unknown'

        return call

    @staticmethod
    def make_call_from_dead_channel(channel):
        event_variables = channel.json['channelvars']
        call = Call(channel.id)
        call.conversation_id = event_variables.get('CHANNEL(linkedid)') or None
        call.is_video = event_variables.get('CHANNEL(videonativeformat)') != '(nothing)'
        call.creation_time = channel.json['creationtime']
        call.status = channel.json['state']
        call.caller_id_name = channel.json['caller']['name']
        call.caller_id_number = channel.json['caller']['number']
        call.peer_caller_id_name = channel.json['connected']['name']
        call.peer_caller_id_number = channel.json['connected']['number']
        call.user_uuid = event_variables.get('WAZO_DEREFERENCED_USERUUID') or event_variables.get('XIVO_USERUUID') or None
        call.tenant_uuid = event_variables.get('WAZO_TENANT_UUID') or None
        call.dialed_extension = event_variables.get('WAZO_ENTRY_EXTEN') or None
        call.bridges = []
        call.talking_to = {}
        call.sip_call_id = event_variables.get('WAZO_SIP_CALL_ID') or None
        call.line_id = event_variables.get('WAZO_LINE_ID') or None
        call.direction = event_variables.get('WAZO_CONVERSATION_DIRECTION') or 'unknown'

        return call

    def send_dtmf(self, call_id, digits):
        try:
            self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)
        for digit in digits:
            ami.dtmf(self._ami, call_id, digit)

    def send_dtmf_user(self, call_id, user_uuid, digits):
        self._verify_user(call_id, user_uuid)
        self.send_dtmf(call_id, digits)

    def hold(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        protocol_interface = protocol_interface_from_channel(channel.json['name'])

        self._phoned_client.hold_endpoint(protocol_interface.interface)

    def hold_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.hold(call_id)

    def unhold(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        protocol_interface = protocol_interface_from_channel(channel.json['name'])

        self._phoned_client.unhold_endpoint(protocol_interface.interface)

    def unhold_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.unhold(call_id)

    def _find_channel_to_record(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        channel_name = channel.json['name']
        is_side_1_of_local = channel_name.startswith('Local/') and channel_name.endswith(';1')
        if not is_side_1_of_local:
            return channel

        try:
            is_group_callee = channel.getChannelVar(variable='WAZO_RECORD_GROUP_CALLEE')['value'] == '1'
        except ARINotFound:
            is_group_callee = False

        is_agent_callback = 'agentcallback' in channel_name

        if not (is_group_callee or is_agent_callback):
            return channel

        local_chan_uuid = channel.json['channelvars']['WAZO_LOCAL_CHAN_MATCH_UUID']
        if not local_chan_uuid:
            return channel

        for potential_channel in self._ari.channels.list():
            if potential_channel.json['name'].startswith('Local'):
                continue
            if potential_channel.json['channelvars']['WAZO_LOCAL_CHAN_MATCH_UUID'] != local_chan_uuid:
                continue
            if potential_channel.json['channelvars']['WAZO_CALL_RECORD_SIDE'] == 'caller':
                continue

            logger.debug(
                'we are going to record the "real" channel instead of the local channel %s',
                channel.json['name']
            )
            return potential_channel

        return channel

    def record_start(self, call_id):
        channel = self._find_channel_to_record(call_id)
        channel_variables = channel.json['channelvars']

        if channel_variables['WAZO_CALL_RECORD_ACTIVE'] == '1':
            return

        filename = CALL_RECORDING_FILENAME_TEMPLATE.format(
            tenant_uuid=channel_variables['WAZO_TENANT_UUID'],
            recording_uuid=str(uuid.uuid4()),
        )

        try:
            mix_monitor_options = channel.getChannelVar(variable='WAZO_MIXMONITOR_OPTIONS')['value']
        except ARINotFound:
            mix_monitor_options = None

        ami.record_start(self._ami, channel.id, filename, mix_monitor_options or None)

    def record_start_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.record_start(call_id)

    def record_stop(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        call_record_active = channel.json['channelvars'].get('WAZO_CALL_RECORD_ACTIVE')
        if not call_record_active or call_record_active == '0':
            return

        ami.record_stop(self._ami, call_id)

    def record_stop_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.record_stop(call_id)

    def answer(self, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        protocol_interface = protocol_interface_from_channel(channel.json['name'])

        self._phoned_client.answer_endpoint(protocol_interface.interface)

    def answer_user(self, call_id, user_uuid):
        self._verify_user(call_id, user_uuid)
        self.answer(call_id)

    def set_answered_time(self, channel_id):
        try:
            set_channel_id_var_sync(
                self._ari,
                channel_id,
                'WAZO_ANSWER_TIME',
                datetime.datetime.now(LOCAL_TIMEZONE).isoformat(),
                bypass_stasis=True,
            )
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            raise NoSuchCall(channel_id)

    def conversation_direction_from_channels(self, channels):
        all_directions = []

        for channel in channels:
            try:
                call_direction = (
                    self._ari.channels.getChannelVar(channelId=channel.id, variable='WAZO_CALL_DIRECTION')['value']
                )
            except ARINotFound:
                continue
            else:
                if call_direction:
                    all_directions.append(call_direction)

        return self._conversation_direction_from_directions(all_directions)

    def _conversation_direction_from_directions(self, directions):
        if 'outbound' in directions and 'inbound' in directions:
            return 'unknown'

        if 'outbound' in directions:
            return 'outbound'

        if 'inbound' in directions:
            return 'inbound'

        # NOTE(afournier): internal should have the lowest priority
        if 'internal' in directions:
            return 'internal'

        return 'unknown'

    def _verify_user(self, call_id, user_uuid):
        channel = Channel(call_id, self._ari)
        if not channel.exists() or channel.is_local():
            raise NoSuchCall(call_id)

        if channel.user() != user_uuid:
            raise UserPermissionDenied(user_uuid, {'call': call_id})
