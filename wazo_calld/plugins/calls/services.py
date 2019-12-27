# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME
from wazo_calld.exceptions import InvalidExtension
from wazo_calld.exceptions import UserPermissionDenied
from wazo_calld.helpers import ami
from wazo_calld.helpers.ari_ import Channel
from wazo_calld.helpers.confd import User

from .call import Call
from .exceptions import CallConnectError
from .exceptions import CallCreationError
from .exceptions import NoSuchCall
from .state_persistor import ReadOnlyStatePersistor
from .dial_echo import DialEchoTimeout

logger = logging.getLogger(__name__)


class CallsService:

    def __init__(self, amid_client, ari_config, ari, confd_client, dial_echo_manager):
        self._ami = amid_client
        self._ari_config = ari_config
        self._ari = ari
        self._confd = confd_client
        self._dial_echo_manager = dial_echo_manager
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
            raise InvalidExtension(requested_context, requested_extension)

        source_user = request['source']['user']
        variables = request.get('variables', {})
        dial_echo_request_id = None

        if request['source']['from_mobile']:
            source_mobile = User(source_user, self._confd).mobile_phone_number()
            if not source_mobile:
                raise CallCreationError('User has no mobile phone number', details={'user': source_user})
            source_context = User(source_user, self._confd).main_line().context()
            if not ami.extension_exists(self._ami, source_context, source_mobile, priority=1):
                details = {'user': source_user,
                           'mobile_exten': source_mobile,
                           'mobile_context': source_context}
                raise CallCreationError('User has invalid mobile phone number', details=details)
            endpoint = 'local/s@wazo-originate-mobile-leg1/n'
            context, extension, priority = 'wazo-originate-mobile-leg2', 's', 1

            variables.setdefault('_XIVO_USERUUID', source_user)
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
                                                   context=context,
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
                endpoint = User(source_user, self._confd).line(request['source']['line_id']).interface()
            else:
                endpoint = User(source_user, self._confd).main_line().interface()

            context, extension, priority = requested_context, requested_extension, requested_priority

            variables.setdefault('XIVO_FIX_CALLERID', '1')
            variables.setdefault('CONNECTEDLINE(name)', extension)
            variables.setdefault('CONNECTEDLINE(num)', '' if extension.startswith('#') else extension)
            variables.setdefault('CALLERID(name)', extension)
            variables.setdefault('CALLERID(num)', extension)
            variables.setdefault('WAZO_CHANNEL_DIRECTION', 'to-wazo')

            channel = self._ari.channels.originate(endpoint=endpoint,
                                                   extension=extension,
                                                   context=context,
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
                       'from_mobile': request['from_mobile']},
            'variables': request['variables']
        }
        if 'line_id' in request:
            new_request['source']['line_id'] = request['line_id']
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

    def hangup_user(self, call_id, user_uuid):
        channel = Channel(call_id, self._ari)
        if not channel.exists() or channel.is_local():
            raise NoSuchCall(call_id)

        if channel.user() != user_uuid:
            raise UserPermissionDenied(user_uuid, {'call': call_id})

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
        channel_helper = Channel(channel.id, ari)
        call = Call(channel.id)
        call.creation_time = channel.json['creationtime']
        call.status = channel.json['state']
        call.caller_id_name = channel.json['caller']['name']
        call.caller_id_number = channel.json['caller']['number']
        call.peer_caller_id_name = channel.json['connected']['name']
        call.peer_caller_id_number = channel.json['connected']['number']
        call.user_uuid = channel_helper.user()
        call.on_hold = channel_helper.on_hold()
        call.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]
        call.talking_to = {connected_channel.id: connected_channel.user()
                           for connected_channel in channel_helper.connected_channels()}
        call.is_caller = channel_helper.is_caller()
        call.dialed_extension = channel_helper.dialed_extension()
        call.sip_call_id = channel_helper.sip_call_id()

        return call

    def make_call_from_ami_event(self, event):
        event_variables = event['ChanVariable']
        call = Call(event['Uniqueid'])
        call.status = event['ChannelStateDesc']
        call.caller_id_name = event['CallerIDName']
        call.caller_id_number = event['CallerIDNum']
        call.peer_caller_id_name = event['ConnectedLineName']
        call.peer_caller_id_number = event['ConnectedLineNum']
        call.user_uuid = event_variables.get('WAZO_DEREFERENCED_USERUUID') or event_variables.get('XIVO_USERUUID') or None
        call.dialed_extension = event_variables.get('XIVO_BASE_EXTEN') or None
        call.bridges = []
        call.talking_to = {}
        call.sip_call_id = event_variables.get('WAZO_SIP_CALL_ID') or None

        return call
