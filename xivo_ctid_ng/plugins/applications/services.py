# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from requests import HTTPError
from ari.exceptions import ARINotFound
from xivo_ctid_ng.helpers import ami
from xivo_ctid_ng.exceptions import InvalidExtension
from .confd import Application
from .models import (
    make_call_from_channel,
    make_node_from_bridge,
)
from .exceptions import (
    CallAlreadyInNode,
    NoSuchCall,
    NoSuchNode,
)
from .stasis import AppNameHelper


class ApplicationService(object):

    def __init__(self, ari, confd, amid, notifier):
        self._ari = ari
        self._confd = confd
        self._amid = amid
        self._notifier = notifier

    def channel_answer(self, application_uuid, channel):
        channel.answer()
        variables = self.get_channel_variables(channel)
        call = make_call_from_channel(channel, ari=self._ari, variables=variables)
        self._notifier.call_entered(application_uuid, call)

    def create_destination_node(self, application):
        try:
            bridge = self._ari.bridges.get(bridgeId=application['uuid'])
        except ARINotFound:
            bridge_type = application['destination_options']['type']
            bridge = self._ari.bridges.createWithId(
                bridgeId=application['uuid'],
                name=application['uuid'],
                type=bridge_type,
            )
            node = make_node_from_bridge(bridge)
            self._notifier.destination_node_created(application['uuid'], node)

    def create_node_with_calls(self, application_uuid, call_ids):
        bridges = self._ari.bridges.list()
        for bridge in bridges:
            if str(bridge.id) == str(application_uuid):
                # Allow to switch channel from default bridge
                continue

            for call_id in call_ids:
                if call_id in bridge.json['channels']:
                    raise CallAlreadyInNode(application_uuid, bridge.id, call_id)

        bridge = self._ari.bridges.create(name=application_uuid, type='mixing')
        node = make_node_from_bridge(bridge)
        self._notifier.node_created(application_uuid, node)

        self.join_node(application_uuid, bridge.id, call_ids)
        node = make_node_from_bridge(bridge.get())
        return node

    def get_application(self, application_uuid):
        return Application(application_uuid, self._confd).get()

    def get_channel_variables(self, channel):
        command = 'core show channel {}'.format(channel.json['name'])
        result = self._amid.command(command)
        return {var: val for var, val in self._extract_variables(result['response'])}

    def get_node(self, node_uuid):
        try:
            bridge = self._ari.bridges.get(bridgeId=node_uuid)
        except ARINotFound:
            raise NoSuchNode(node_uuid)

        return make_node_from_bridge(bridge)

    def join_destination_node(self, channel_id, application):
        self.join_node(application['uuid'], application['uuid'], [channel_id])
        moh = application['destination_options'].get('music_on_hold')
        if moh:
            self._ari.bridges.startMoh(bridgeId=application['uuid'], mohClass=moh)

    def join_node(self, application_uuid, node_uuid, call_ids):
        for call_id in call_ids:
            try:
                self._ari.bridges.addChannel(bridgeId=node_uuid, channel=call_id)
            except HTTPError as e:
                response = getattr(e, 'response', None)
                status_code = getattr(response, 'status_code', None)
                if status_code == 400:
                    raise NoSuchCall(call_id, 400)
                elif status_code == 404:
                    raise NoSuchNode(node_uuid)
                raise

    def list_calls(self, application_uuid):
        try:
            channel_ids = self._ari.applications.get(
                applicationName=AppNameHelper.to_name(application_uuid)
            )['channel_ids']
        except ARINotFound:
            return

        for channel_id in channel_ids:
            try:
                channel = self._ari.channels.get(channelId=channel_id)
                variables = self.get_channel_variables(channel)
                yield make_call_from_channel(channel, ari=self._ari, variables=variables)
            except ARINotFound:
                continue

    def list_nodes(self, application_uuid):
        try:
            bridges = self._ari.bridges.list()
        except ARINotFound:
            return

        for bridge in bridges:
            if str(bridge.json['name']) != str(application_uuid):
                continue
            yield make_node_from_bridge(bridge)

    def originate(self, application_uuid, node_uuid, exten, context, autoanswer):
        if not ami.extension_exists(self._amid, context, exten, 1):
            raise InvalidExtension(context, exten)

        endpoint = 'Local/{}@{}/n'.format(exten, context)

        app_args = ['originate']
        if node_uuid:
            app_args.append(str(node_uuid))

        originate_kwargs = {
            'endpoint': endpoint,
            'app': AppNameHelper.to_name(application_uuid),
            'appArgs': ','.join(app_args),
            'variables': {'variables': {'WAZO_APP_UUID': str(application_uuid)}}
        }

        if autoanswer:
            originate_kwargs['variables']['variables']['WAZO_AUTO_ANSWER'] = '1'

        channel = self._ari.channels.originate(**originate_kwargs)
        variables = self.get_channel_variables(channel)
        return make_call_from_channel(
            channel,
            ari=self._ari,
            variables=variables,
            node_uuid=node_uuid,
        )

    def originate_answered(self, application_uuid, channel):
        channel.answer()
        variables = self.get_channel_variables(channel)
        call = make_call_from_channel(channel, ari=self._ari, variables=variables)
        self._notifier.call_initiated(application_uuid, call)

    @staticmethod
    def _extract_variables(lines):
        prefix = 'X_WAZO_'
        for line in lines:
            if not line.startswith(prefix):
                continue
            yield line.replace(prefix, '').split('=', 1)
