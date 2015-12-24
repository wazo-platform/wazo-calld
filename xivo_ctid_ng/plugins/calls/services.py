# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import requests

from contextlib import contextmanager
from xivo_confd_client import Client as ConfdClient

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME

from .call import Call
from .exceptions import AsteriskARIUnreachable
from .exceptions import InvalidUserUUID
from .exceptions import NoSuchCall
from .exceptions import UserHasNoLine
from .exceptions import XiVOConfdUnreachable

logger = logging.getLogger(__name__)


@contextmanager
def new_confd_client(config):
    yield ConfdClient(**config)


def not_found(error):
    return error.response is not None and error.response.status_code == 404


class CallsService(object):

    def __init__(self, ari_config, confd_config, ari):
        self._ari_config = ari_config
        self._confd_config = confd_config
        self._ari = ari

    def set_confd_token(self, confd_token):
        self._confd_config['token'] = confd_token

    def list_calls(self, application_filter=None, application_instance_filter=None):
        ari = self._ari.client
        try:
            channels = ari.channels.list()
        except requests.RequestException as e:
            raise AsteriskARIUnreachable(self._ari_config, e)

        if application_filter:
            try:
                channel_ids = ari.applications.get(applicationName=application_filter)['channel_ids']
            except requests.HTTPError as e:
                if not_found(e):
                    channel_ids = []
                else:
                    raise

            channels = [channel for channel in channels if channel.id in channel_ids]

            if application_instance_filter:
                app_instance_channels = []
                for channel in channels:
                    try:
                        channel_app_instance = ari.channels.getChannelVar(channelId=channel.id, variable='XIVO_STASIS_ARGS')['value']
                    except requests.HTTPError as e:
                        if not_found(e):
                            continue
                        raise
                    if channel_app_instance == application_instance_filter:
                        app_instance_channels.append(channel)
                channels = app_instance_channels

        return [self.make_call_from_channel(ari, channel) for channel in channels]

    def originate(self, request):
        source_user = request['source']['user']
        endpoint = self._endpoint_from_user_uuid(source_user)

        ari = self._ari.client
        try:
            channel = ari.channels.originate(endpoint=endpoint,
                                             extension=request['destination']['extension'],
                                             context=request['destination']['context'],
                                             priority=request['destination']['priority'],
                                             variables={'variables': request.get('variables', {})})
            return channel.id
        except requests.RequestException as e:
            raise AsteriskARIUnreachable(self._ari_config, e)

    def get(self, call_id):
        channel_id = call_id
        ari = self._ari.client
        try:
            channel = ari.channels.get(channelId=channel_id)
        except requests.HTTPError as e:
            if not_found(e):
                raise NoSuchCall(channel_id)
            raise AsteriskARIUnreachable(self._ari_config, e)

        return self.make_call_from_channel(ari, channel)

    def hangup(self, call_id):
        channel_id = call_id
        ari = self._ari.client
        try:
            ari.channels.get(channelId=channel_id)
        except requests.HTTPError as e:
            if not_found(e):
                raise NoSuchCall(channel_id)
            raise AsteriskARIUnreachable(self._ari_config, e)

        ari.channels.hangup(channelId=channel_id)

    def connect_user(self, call_id, user_id):
        channel_id = call_id
        endpoint = self._endpoint_from_user_uuid(user_id)

        ari = self._ari.client
        try:
            channel = ari.channels.get(channelId=channel_id)
        except requests.HTTPError as e:
            if not_found(e):
                raise NoSuchCall(channel_id)

        new_channel = ari.channels.originate(endpoint=endpoint,
                                             app=APPLICATION_NAME,
                                             appArgs=['dialed_from', channel_id])

        # if the caller hangs up, we cancel our originate
        originate_canceller = channel.on_event('StasisEnd', lambda _, __: self.hangup(new_channel.id))
        # if the callee accepts, we don't have to cancel anything
        new_channel.on_event('StasisStart', lambda _, __: originate_canceller.close())
        # if the callee refuses, leave the caller as it is

        return new_channel.id

    def make_call_from_channel(self, ari, channel):
        call = Call(channel.id, channel.json['creationtime'])
        call.status = channel.json['state']
        call.caller_id_name = channel.json['caller']['name']
        call.caller_id_number = channel.json['caller']['number']
        call.user_uuid = self._get_uuid_from_channel_id(ari, channel.id)
        call.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]

        call.talking_to = dict()
        for channel_id in self._get_channel_ids_from_bridges(ari, call.bridges):
            talking_to_user_uuid = self._get_uuid_from_channel_id(ari, channel_id)
            call.talking_to[channel_id] = talking_to_user_uuid
        call.talking_to.pop(channel.id, None)

        return call

    def _endpoint_from_user_uuid(self, uuid):
        with new_confd_client(self._confd_config) as confd:
            try:
                user_id = confd.users.get(uuid)['id']
                user_lines_of_user = confd.users.relations(user_id).list_lines()['items']
            except requests.HTTPError as e:
                if not_found(e):
                    raise InvalidUserUUID(uuid)
                raise
            except requests.RequestException as e:
                raise XiVOConfdUnreachable(self._confd_config, e)

            main_line_ids = [user_line['line_id'] for user_line in user_lines_of_user if user_line['main_line'] is True]
            if not main_line_ids:
                raise UserHasNoLine(uuid)
            line_id = main_line_ids[0]
            line = confd.lines.get(line_id)

        endpoint = "{}/{}".format(line['protocol'], line['name'])
        if endpoint:
            return endpoint

        return None

    def _get_uuid_from_channel_id(self, ari, channel_id):
        try:
            user_id = ari.channels.getChannelVar(channelId=channel_id, variable='XIVO_USERID')['value']
        except requests.HTTPError as e:
            if not_found(e):
                return None
            raise

        with new_confd_client(self._confd_config) as confd:
            try:
                uuid = confd.users.get(user_id)['uuid']
                return uuid
            except requests.HTTPError as e:
                logger.error('Error fetching user %s from xivo-confd (%s): %s', user_id, self._confd_config, e)
            except requests.RequestException as e:
                raise XiVOConfdUnreachable(self._confd_config, e)

        return None

    def _get_channel_ids_from_bridges(self, ari, bridges):
        result = set()
        for bridge_id in bridges:
            try:
                channels = ari.bridges.get(bridgeId=bridge_id).json['channels']
            except requests.RequestException as e:
                logger.error(e)
                channels = set()
            result.update(channels)
        return result
