# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    def subscribe(self, consumer):
        consumer.on_ami_event('Hangup', self.on_hangup)
        consumer.on_ami_event('Newchannel', self.on_new_channel)
        consumer.on_ami_event('PeerStatus', self.on_peer_status)
        consumer.on_ami_event('Registry', self.on_registry)
        consumer.on_event('trunk_created', self.on_trunk_created)
        consumer.on_event('trunk_updated', self.on_trunk_updated)
        consumer.on_event('trunk_deleted', self.on_trunk_deleted)

    def on_hangup(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        self._endpoints_service.remove_call(techno, name, unique_id)

    def on_new_channel(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        self._endpoints_service.add_call(techno, name, unique_id)

    def on_peer_status(self, event):
        techno, name = event['Peer'].split('/', 1)
        status = event['PeerStatus']

        kwargs = {}
        if techno == 'PJSIP' and status == 'Reachable':
            kwargs['registered'] = True
        elif techno == 'PJSIP' and status == 'Unreachable':
            kwargs['registered'] = False

        self._endpoints_service.update_line_endpoint(techno, name, **kwargs)

    def on_registry(self, event):
        techno = event['ChannelType']
        begin, _ = event['Username'].split('@', 1)
        _, username = begin.split(':', 1)
        registered = event['Status'] == 'Registered'

        self._endpoints_service.update_trunk_endpoint(techno, username, registered=registered)

    def on_trunk_created(self, event):
        self._endpoints_service.add_trunk(event['id'])

    def on_trunk_updated(self, event):
        self._endpoints_service.update_trunk(event['id'])

    def on_trunk_deleted(self, event):
        self._endpoints_service.delete_trunk(event['id'])

    def _techno_name_from_channel(self, channel):
        techno, end = channel.split('/', 1)
        name, _ = end.rsplit('-', 1)
        return techno, name
