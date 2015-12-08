# -*- coding: utf-8 -*-
# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import ari
import logging
import requests

from flask import current_app
from flask import request
from contextlib import contextmanager

from xivo_confd_client import Client as ConfdClient
from xivo_ctid_ng.core.rest_api import AuthResource

from .exceptions import AsteriskARIUnreachable
from .exceptions import CallCreationError
from .exceptions import InvalidUserUUID
from .exceptions import NoSuchCall
from .exceptions import UserHasNoLine
from .exceptions import XiVOConfdUnreachable
from . import validator

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


def endpoint_from_user_uuid(uuid):
    with new_confd_client(current_app.config['confd']) as confd:
        try:
            user_id = confd.users.get(uuid)['id']
            user_lines_of_user = confd.users.relations(user_id).list_lines()['items']
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise InvalidUserUUID(uuid)
            raise
        except requests.RequestException as e:
            raise XiVOConfdUnreachable(current_app.config['confd'], e)

        main_line_ids = [user_line['line_id'] for user_line in user_lines_of_user if user_line['main_line'] is True]
        if not main_line_ids:
            raise UserHasNoLine(uuid)
        line_id = main_line_ids[0]
        line = confd.lines.get(line_id)

    endpoint = "{}/{}".format(line['protocol'], line['name'])
    if endpoint:
        return endpoint

    return None


def get_uuid_from_channel_id(ari, channel_id):
    try:
        user_id = ari.channels.getChannelVar(channelId=channel_id, variable='XIVO_USERID')['value']
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise

    with new_confd_client(current_app.config['confd']) as confd:
        try:
            uuid = confd.users.get(user_id)['uuid']
            return uuid
        except requests.HTTPError as e:
            logger.error('Error fetching user %s from xivo-confd (%s): %s', user_id, current_app.config['confd'], e)
        except requests.RequestException as e:
            raise XiVOConfdUnreachable(current_app.config['confd'], e)

    return None


class Call(object):

    def __init__(self, id_, creation_time):
        self.id_ = id_
        self.creation_time = creation_time
        self.bridges = []
        self.status = 'Down'
        self.talking_to = []
        self.user_uuid = None

    def to_dict(self):
        return {
            'bridges': self.bridges,
            'call_id': self.id_,
            'creation_time': self.creation_time,
            'status': self.status,
            'talking_to': self.talking_to,
            'user_uuid': self.user_uuid,
        }


def get_channel_ids_from_bridges(ari, bridges):
    result = set()
    for bridge_id in bridges:
        try:
            channels = ari.bridges.get(bridgeId=bridge_id).json['channels']
        except requests.RequestException as e:
            logger.error(e)
            channels = set()
        result.update(channels)
    return result


class CallsResource(AuthResource):

    def get(self):
        token = request.headers['X-Auth-Token']
        current_app.config['confd']['token'] = token
        application_filter = request.args.get('application')

        calls = []
        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                channels = ari.channels.list()
            except requests.RequestException as e:
                raise AsteriskARIUnreachable(current_app.config['ari']['connection'], e)

            if application_filter:
                try:
                    channel_ids = ari.applications.get(applicationName=application_filter)['channel_ids']
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code == 404:
                        channel_ids = []

                channels = [channel for channel in channels if channel.id in channel_ids]

            for channel in channels:
                result_call = Call(channel.id, channel.json['creationtime'])
                result_call.status = channel.json['state']
                result_call.user_uuid = get_uuid_from_channel_id(ari, channel.id)
                result_call.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]

                result_call.talking_to = dict()
                for channel_id in get_channel_ids_from_bridges(ari, result_call.bridges):
                    talking_to_user_uuid = get_uuid_from_channel_id(ari, channel_id)
                    result_call.talking_to[channel_id] = talking_to_user_uuid
                result_call.talking_to.pop(channel.id, None)

                calls.append(result_call)

        return {
            'items': [call.to_dict() for call in calls],
        }, 200

    def post(self):
        token = request.headers['X-Auth-Token']
        current_app.config['confd']['token'] = token

        request_body = request.json
        validator.validate_originate(request_body)
        source_user = request_body['source']['user']
        try:
            endpoint = endpoint_from_user_uuid(source_user)
        except InvalidUserUUID:
            raise CallCreationError('Wrong source user', {'source': {'user': source_user}})
        except UserHasNoLine:
            raise CallCreationError('User has no line', {'source': {'user': source_user}})

        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                channel = ari.channels.originate(endpoint=endpoint,
                                                 extension=request_body['destination']['extension'],
                                                 context=request_body['destination']['context'],
                                                 priority=request_body['destination']['priority'],
                                                 variables={'variables': request_body.get('variables', {})})
            except requests.RequestException as e:
                raise AsteriskARIUnreachable(current_app.config['ari']['connection'], e)

            return {'call_id': channel.id}, 201

        return None


class CallResource(AuthResource):

    def get(self, call_id):
        channel_id = call_id
        token = request.headers['X-Auth-Token']
        current_app.config['confd']['token'] = token

        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                channel = ari.channels.get(channelId=channel_id)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    raise NoSuchCall(channel_id)
                raise AsteriskARIUnreachable(current_app.config['ari']['connection'], e)

            result = Call(channel.id, channel.json['creationtime'])
            result.status = channel.json['state']
            result.user_uuid = get_uuid_from_channel_id(ari, channel_id)
            result.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]
            result.talking_to = dict()
            for bridge_id in result.bridges:
                talking_to_channel_ids = ari.bridges.get(bridgeId=bridge_id).json['channels']
                for talking_to_channel_id in talking_to_channel_ids:
                    talking_to_user_uuid = get_uuid_from_channel_id(ari, talking_to_channel_id)
                    result.talking_to[talking_to_channel_id] = talking_to_user_uuid
            del result.talking_to[channel_id]

        return result.to_dict()

    def delete(self, call_id):
        channel_id = call_id
        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                ari.channels.get(channelId=channel_id)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    raise NoSuchCall(channel_id)
                raise AsteriskARIUnreachable(current_app.config['ari']['connection'], e)

        ari.channels.hangup(channelId=channel_id)

        return None, 204
