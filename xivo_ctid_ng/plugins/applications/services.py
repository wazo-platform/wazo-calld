# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from ari.exceptions import ARINotFound
from .confd import Application
from .models import (
    make_call_from_channel,
    make_node_from_bridge,
)


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

    def get_application(self, application_uuid):
        return Application(application_uuid, self._confd).get()

    def get_channel_variables(self, channel):
        command = 'core show channel {}'.format(channel.json['name'])
        result = self._amid.command(command)
        return {var: val for var, val in self._extract_variables(result['response'])}

    def join_destination_node(self, channel_id, application):
        self.create_destination_node(application)
        self.join_node(application['uuid'], application['uuid'], [channel_id])
        moh = application['destination_options']['music_on_hold']
        if moh:
            self._ari.bridges.startMoh(bridgeId=application['uuid'], mohClass=moh)

    def join_node(self, application_uuid, node_uuid, call_ids):
        for call_id in call_ids:
            self._ari.bridges.addChannel(bridgeId=node_uuid, channel=call_id)

    @staticmethod
    def _extract_variables(lines):
        prefix = 'X_WAZO_'
        for line in lines:
            if not line.startswith(prefix):
                continue
            yield line.replace(prefix, '').split('=', 1)
