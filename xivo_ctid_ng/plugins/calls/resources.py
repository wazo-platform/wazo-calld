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

from .exceptions import XiVOConfdUnreachable, NoSuchCall

logger = logging.getLogger(__name__)


@contextmanager
def new_confd_client(config):
    yield ConfdClient(**config)


@contextmanager
def new_ari_client(config):
    yield ari.connect(**config)


def endpoint_from_user_uuid(uuid):
    with new_confd_client(current_app.config['confd']) as confd:
        try:
            user_id = confd.users.get(uuid)['id']
            line_id = confd.users.relations(user_id).list_lines()['items'][0]['line_id']
            line = confd.lines.get(line_id)
        except requests.RequestException as e:
            raise XiVOConfdUnreachable(current_app.config['confd'], e)
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


class Calls(AuthResource):

    def get(self):
        token = request.headers['X-Auth-Token']
        current_app.config['confd']['token'] = token

        result = []
        with new_ari_client(current_app.config['ari']['connection']) as ari:
            channels = ari.channels.list()
            for channel in channels:
                user_uuid = get_uuid_from_channel_id(ari, channel.id)
                bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]

                talking_to = dict()
                for channel_id in get_channel_ids_from_bridges(ari, bridges):
                    talking_to_user_uuid = get_uuid_from_channel_id(ari, channel_id)
                    talking_to[channel_id] = talking_to_user_uuid
                talking_to.pop(channel.id, None)

                result.append({
                    'bridges': bridges,
                    'call_id': channel.id,
                    'status': channel.json['state'],
                    'talking_to': talking_to,
                    'user_uuid': user_uuid,
                })

        return result, 200

    def post(self):
        token = request.headers['X-Auth-Token']
        current_app.config['confd']['token'] = token

        request_body = request.json
        endpoint = endpoint_from_user_uuid(request_body['source']['user'])
        with new_ari_client(current_app.config['ari']['connection']) as ari:
            channel = ari.channels.originate(endpoint=endpoint,
                                          extension=request_body['destination']['extension'],
                                          context=request_body['destination']['context'],
                                          priority=request_body['destination']['priority'])
            return {'call_id': channel.id}, 201

        return None


class Call(AuthResource):

    def get(self, call_id):
        channel_id = call_id
        token = request.headers['X-Auth-Token']
        current_app.config['confd']['token'] = token

        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                channel = ari.channels.get(channelId=channel_id)
            except requests.RequestException:
                raise NoSuchCall(channel_id)
            user_uuid = get_uuid_from_channel_id(ari, channel_id)

            bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]

            talking_to = dict()
            for bridge_id in bridges:
                talking_to_channel_ids = ari.bridges.get(bridgeId=bridge_id).json['channels']
                for talking_to_channel_id in talking_to_channel_ids:
                    talking_to_user_uuid = get_uuid_from_channel_id(ari, talking_to_channel_id)
                    talking_to[talking_to_channel_id] = talking_to_user_uuid
            del talking_to[channel_id]

        status = channel.json['state']

        return {
            'bridges': bridges,
            'call_id': channel.id,
            'status': status,
            'talking_to': dict(talking_to),
            'user_uuid': user_uuid,
        }

    def delete(self, call_id):
        channel_id = call_id
        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                channel = ari.channels.get(channelId=channel_id)
            except requests.RequestException as e:
                raise NoSuchCall(channel_id)

        ari.channels.hangup(channelId=channel_id)

        return None, 204
