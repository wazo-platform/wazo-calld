# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import ari
import logging
import requests

from contextlib import contextmanager

from xivo_confd_client import Client as ConfdClient

from .call import Call
from .exceptions import AsteriskARIUnreachable
from .exceptions import CallCreationError
from .exceptions import InvalidUserUUID
from .exceptions import NoSuchCall
from .exceptions import UserHasNoLine
from .exceptions import XiVOConfdUnreachable

logger = logging.getLogger(__name__)


@contextmanager
def new_confd_client(config):
    yield ConfdClient(**config)


@contextmanager
def new_ari_client(config):
    try:
        yield ari.connect(**config)
    except requests.ConnectionError as e:
        raise AsteriskARIUnreachable(config, e)


class CallsService(object):

    def __init__(self, ari_config, confd_config):
        self._ari_config = ari_config
        self._confd_config = confd_config

    def set_confd_token(self, confd_token):
        self._confd_config['token'] = confd_token

    def list_calls(self, application_filter=None, application_instance_filter=None):
        calls = []
        with new_ari_client(self._ari_config) as ari:
            try:
                channels = ari.channels.list()
            except requests.RequestException as e:
                raise AsteriskARIUnreachable(self._ari_config, e)

            if application_filter:
                try:
                    channel_ids = ari.applications.get(applicationName=application_filter)['channel_ids']
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code == 404:
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
                            if e.response is not None and e.response.status_code == 404:
                                continue
                            raise
                        if channel_app_instance == application_instance_filter:
                            app_instance_channels.append(channel)
                    channels = app_instance_channels

            for channel in channels:
                result_call = Call(channel.id, channel.json['creationtime'])
                result_call.status = channel.json['state']
                result_call.caller_id_name = channel.json['caller']['name']
                result_call.caller_id_number = channel.json['caller']['number']
                result_call.user_uuid = self._get_uuid_from_channel_id(ari, channel.id)
                result_call.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]

                result_call.talking_to = dict()
                for channel_id in self._get_channel_ids_from_bridges(ari, result_call.bridges):
                    talking_to_user_uuid = self._get_uuid_from_channel_id(ari, channel_id)
                    result_call.talking_to[channel_id] = talking_to_user_uuid
                result_call.talking_to.pop(channel.id, None)

                calls.append(result_call)
        return calls

    def originate(self, request):
        source_user = request['source']['user']
        try:
            endpoint = self._endpoint_from_user_uuid(source_user)
        except InvalidUserUUID:
            raise CallCreationError('Wrong source user', {'source': {'user': source_user}})
        except UserHasNoLine:
            raise CallCreationError('User has no line', {'source': {'user': source_user}})

        with new_ari_client(self._ari_config) as ari:
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
        with new_ari_client(self._ari_config) as ari:
            try:
                channel = ari.channels.get(channelId=channel_id)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    raise NoSuchCall(channel_id)
                raise AsteriskARIUnreachable(self._ari_config, e)

            result = Call(channel.id, channel.json['creationtime'])
            result.status = channel.json['state']
            result.caller_id_name = channel.json['caller']['name']
            result.caller_id_number = channel.json['caller']['number']
            result.user_uuid = self._get_uuid_from_channel_id(ari, channel_id)
            result.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]
            result.talking_to = dict()
            for bridge_id in result.bridges:
                talking_to_channel_ids = ari.bridges.get(bridgeId=bridge_id).json['channels']
                for talking_to_channel_id in talking_to_channel_ids:
                    talking_to_user_uuid = self._get_uuid_from_channel_id(ari, talking_to_channel_id)
                    result.talking_to[talking_to_channel_id] = talking_to_user_uuid
            del result.talking_to[channel_id]

        return result

    def hangup(self, call_id):
        channel_id = call_id
        with new_ari_client(self._ari_config) as ari:
            try:
                ari.channels.get(channelId=channel_id)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    raise NoSuchCall(channel_id)
                raise AsteriskARIUnreachable(self._ari_config, e)

        ari.channels.hangup(channelId=channel_id)

    def _endpoint_from_user_uuid(self, uuid):
        with new_confd_client(self._confd_config) as confd:
            try:
                user_id = confd.users.get(uuid)['id']
                user_lines_of_user = confd.users.relations(user_id).list_lines()['items']
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
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
            if e.response is not None and e.response.status_code == 404:
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
