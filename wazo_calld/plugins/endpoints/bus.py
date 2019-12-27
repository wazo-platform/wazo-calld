# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, endpoint_status_cache, confd_cache):
        self._endpoint_status_cache = endpoint_status_cache
        self._confd_cache = confd_cache

    def subscribe(self, consumer):
        consumer.on_ami_event('Hangup', self.on_hangup)
        consumer.on_ami_event('Newchannel', self.on_new_channel)
        consumer.on_ami_event('PeerStatus', self.on_peer_status)
        consumer.on_ami_event('Registry', self.on_registry)
        consumer.on_event('custom_endpoint_updated', self.on_endpoint_custom_updated)
        consumer.on_event('iax_endpoint_updated', self.on_trunk_endpoint_iax_updated)
        consumer.on_event('line_deleted', self.on_line_endpoint_deleted)
        consumer.on_event('line_endpoint_custom_associated', self.on_line_endpoint_custom_associated)
        consumer.on_event('line_endpoint_custom_dissociated', self.on_line_endpoint_dissociated)
        consumer.on_event('line_endpoint_sccp_associated', self.on_line_endpoint_sccp_associated)
        consumer.on_event('line_endpoint_sccp_dissociated', self.on_line_endpoint_sccp_dissociated)
        consumer.on_event('line_endpoint_sip_associated', self.on_line_endpoint_sip_associated)
        consumer.on_event('line_endpoint_sip_dissociated', self.on_line_endpoint_dissociated)
        consumer.on_event('sip_endpoint_updated', self.on_endpoint_sip_updated)
        consumer.on_event('trunk_deleted', self.on_trunk_endpoint_deleted)
        consumer.on_event('trunk_endpoint_custom_associated', self.on_trunk_endpoint_custom_associated)
        consumer.on_event('trunk_endpoint_custom_dissociated', self.on_trunk_endpoint_dissociated)
        consumer.on_event('trunk_endpoint_iax_associated', self.on_trunk_endpoint_iax_associated)
        consumer.on_event('trunk_endpoint_iax_dissociated', self.on_trunk_endpoint_dissociated)
        consumer.on_event('trunk_endpoint_sip_associated', self.on_trunk_endpoint_sip_associated)
        consumer.on_event('trunk_endpoint_sip_dissociated', self.on_trunk_endpoint_dissociated)

    def on_hangup(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            endpoint.remove_call(unique_id)

    def on_new_channel(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            endpoint.add_call(unique_id)

    def on_peer_status(self, event):
        techno, name = event['Peer'].split('/', 1)
        status = event['PeerStatus']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            if techno == 'PJSIP' and status == 'Reachable':
                endpoint.registered = True
            elif techno == 'PJSIP' and status == 'Unreachable':
                endpoint.registered = False

    def on_registry(self, event):
        techno = event['ChannelType']
        try:
            begin, _ = event['Username'].split('@', 1)
            _, username = begin.split(':', 1)
        except ValueError:
            return

        trunk = self._confd_cache.get_trunk_by_username(techno, username)
        with self._endpoint_status_cache.update(techno, trunk['name']) as endpoint:
            endpoint.registered = event['Status'] == 'Registered'

    def on_line_endpoint_sip_associated(self, event):
        self._confd_cache.add_line(
            'sip',
            event['line']['id'],
            event['endpoint_sip']['name'],
            event['endpoint_sip']['username'],
            event['line']['tenant_uuid'],
        )

    def on_line_endpoint_sccp_associated(self, event):
        self._confd_cache.add_line(
            'sccp',
            event['line']['id'],
            event['line']['name'],
            None,
            event['line']['tenant_uuid'],
        )

    def on_trunk_endpoint_sip_associated(self, event):
        self._confd_cache.add_trunk(
            'sip',
            event['trunk']['id'],
            event['endpoint_sip']['name'],
            event['endpoint_sip']['username'],
            event['trunk']['tenant_uuid'],
        )

    def on_trunk_endpoint_iax_associated(self, event):
        self._confd_cache.add_trunk(
            'iax',
            event['trunk']['id'],
            event['endpoint_iax']['name'],
            None,
            event['trunk']['tenant_uuid'],
        )

    def on_line_endpoint_custom_associated(self, event):
        self._confd_cache.add_line(
            'custom',
            event['line']['id'],
            event['endpoint_custom']['interface'],
            None,
            event['line']['tenant_uuid'],
        )

    def on_trunk_endpoint_custom_associated(self, event):
        self._confd_cache.add_trunk(
            'custom',
            event['trunk']['id'],
            event['endpoint_custom']['interface'],
            None,
            event['trunk']['tenant_uuid'],
        )

    def on_line_endpoint_dissociated(self, event):
        self._confd_cache.delete_line(event['line']['id'])

    def on_trunk_endpoint_dissociated(self, event):
        self._confd_cache.delete_trunk(event['trunk']['id'])

    def on_line_endpoint_deleted(self, event):
        self._confd_cache.delete_line(event['id'])

    def on_trunk_endpoint_deleted(self, event):
        self._confd_cache.delete_trunk(event['id'])

    def on_endpoint_sip_updated(self, event):
        trunk = event['trunk']
        line = event['line']

        if trunk:
            self._confd_cache.update_trunk(
                'sip',
                event['trunk']['id'],
                event['name'],
                event['username'],
                event['tenant_uuid'],
            )

        if line:
            self._confd_cache.update_line(
                'sip',
                event['line']['id'],
                event['name'],
                event['username'],
                event['tenant_uuid'],
            )

    def on_trunk_endpoint_iax_updated(self, event):
        trunk = event['trunk']
        if not trunk:
            return

        self._confd_cache.update_trunk(
            'iax',
            event['trunk']['id'],
            event['name'],
            None,
            event['tenant_uuid'],
        )

    def on_endpoint_custom_updated(self, event):
        trunk = event['trunk']
        line = event['line']

        if trunk:
            self._confd_cache.update_trunk(
                'custom',
                event['trunk']['id'],
                event['interface'],
                None,
                event['tenant_uuid'],
            )

        if line:
            self._confd_cache.update_line(
                'custom',
                event['line']['id'],
                event['interface'],
                None,
                event['tenant_uuid'],
            )

    def _techno_name_from_channel(self, channel):
        techno, end = channel.split('/', 1)
        name, _ = end.rsplit('-', 1)
        return techno, name
