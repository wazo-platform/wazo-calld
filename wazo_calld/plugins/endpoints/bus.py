# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .identity import LINE, TRUNK, EndpointIdentity

logger = logging.getLogger(__name__)


class EventHandler:
    """Keeps the endpoint status and the endpoint identities up to date.

    wazo-confd is the truth for identities, and Asterisk's configuration lags it
    (it is regenerated and reloaded after wazo-confd's event): an association or an
    update writes the identity its event carries, so that a status event landing
    before the reload is not resolved from the old configuration.
    """

    def __init__(self, endpoint_status_cache, identity_map, identities):
        self._endpoint_status_cache = endpoint_status_cache
        self._identity_map = identity_map
        self._identities = identities

    def subscribe(self, consumer):
        consumer.subscribe('Hangup', self.on_hangup)
        consumer.subscribe('Newchannel', self.on_new_channel)
        consumer.subscribe('PeerStatus', self.on_peer_status)
        consumer.subscribe('Registry', self.on_registry)
        consumer.subscribe('iax_endpoint_updated', self.on_trunk_endpoint_iax_updated)
        consumer.subscribe('line_edited', self.on_line_edited)
        consumer.subscribe('line_deleted', self.on_line_endpoint_deleted)
        consumer.subscribe(
            'line_endpoint_custom_dissociated', self.on_line_endpoint_dissociated
        )
        consumer.subscribe(
            'line_endpoint_sccp_associated', self.on_line_endpoint_sccp_associated
        )
        consumer.subscribe(
            'line_endpoint_sccp_dissociated', self.on_line_endpoint_dissociated
        )
        consumer.subscribe(
            'line_endpoint_sip_associated', self.on_line_endpoint_sip_associated
        )
        consumer.subscribe(
            'line_endpoint_sip_dissociated', self.on_line_endpoint_dissociated
        )
        consumer.subscribe('sip_endpoint_updated', self.on_endpoint_sip_updated)
        consumer.subscribe('trunk_deleted', self.on_trunk_endpoint_deleted)
        consumer.subscribe(
            'trunk_endpoint_custom_associated', self.on_trunk_endpoint_custom_associated
        )
        consumer.subscribe(
            'trunk_endpoint_custom_dissociated', self.on_trunk_endpoint_dissociated
        )
        consumer.subscribe(
            'trunk_endpoint_iax_associated', self.on_trunk_endpoint_iax_associated
        )
        consumer.subscribe(
            'trunk_endpoint_iax_dissociated', self.on_trunk_endpoint_dissociated
        )
        consumer.subscribe(
            'trunk_endpoint_sip_associated', self.on_trunk_endpoint_sip_associated
        )
        consumer.subscribe(
            'trunk_endpoint_sip_dissociated', self.on_trunk_endpoint_dissociated
        )

    def on_hangup(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        if techno == 'Local':
            return

        unique_id = event['Uniqueid']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            endpoint.remove_call(unique_id)

    def on_new_channel(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        if techno == 'Local':
            return

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
        if techno == 'PJSIP':
            name = self._identities.endpoint_of_client_uri(event['Username'])
        elif techno == 'IAX2':
            try:
                begin, _ = event['Username'].split('@', 1)
                _, name = begin.split(':', 1)
            except ValueError:
                return
        else:
            return

        if not name:
            return

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            endpoint.registered = event['Status'] == 'Registered'

    def on_line_endpoint_sip_associated(self, event):
        name = event['endpoint_sip']['name']
        line = event['line']
        self._write_line('PJSIP', name, line['id'], line['tenant_uuid'])
        self._endpoint_status_cache.add_new_sip_endpoint(name)

    def on_line_endpoint_sccp_associated(self, event):
        line = event['line']
        self._write_line('SCCP', line['name'], line['id'], line['tenant_uuid'])

    def on_line_edited(self, event):
        if event['protocol'] != 'sccp':
            return

        self._write_line('SCCP', event['name'], event['id'], event['tenant_uuid'])

    def on_trunk_endpoint_sip_associated(self, event):
        name = event['endpoint_sip']['name']
        trunk = event['trunk']
        self._write_trunk('PJSIP', name, trunk['id'], trunk['tenant_uuid'])
        self._endpoint_status_cache.add_new_sip_endpoint(name)

    def on_trunk_endpoint_iax_associated(self, event):
        name = event['endpoint_iax']['name']
        trunk = event['trunk']
        self._write_trunk('IAX2', name, trunk['id'], trunk['tenant_uuid'])
        self._endpoint_status_cache.add_new_iax_endpoint(name)

    def on_trunk_endpoint_custom_associated(self, event):
        # A custom endpoint's status is never published: only the registrations change
        self._identity_map.forget_client_uris()

    def on_line_endpoint_dissociated(self, event):
        self._identity_map.evict(LINE, event['line']['id'])

    def on_trunk_endpoint_dissociated(self, event):
        self._identity_map.evict(TRUNK, event['trunk']['id'])
        self._identity_map.forget_client_uris()

    def on_line_endpoint_deleted(self, event):
        self._identity_map.evict(LINE, event['id'])

    def on_trunk_endpoint_deleted(self, event):
        for techno, name in self._identity_map.evict(TRUNK, event['id']):
            self._endpoint_status_cache.pop(techno, name)
        self._identity_map.forget_client_uris()

    def on_endpoint_sip_updated(self, event):
        if event['trunk']:
            trunk_id = event['trunk']['id']
            self._write_trunk('PJSIP', event['name'], trunk_id, event['tenant_uuid'])

        if event['line']:
            line_id = event['line']['id']
            self._write_line('PJSIP', event['name'], line_id, event['tenant_uuid'])

    def on_trunk_endpoint_iax_updated(self, event):
        if not event['trunk']:
            return

        trunk_id = event['trunk']['id']
        self._write_trunk('IAX2', event['name'], trunk_id, event['tenant_uuid'])

    def _write_line(self, techno, name, line_id, tenant_uuid):
        identity = EndpointIdentity(LINE, line_id, tenant_uuid)
        self._identity_map.write((techno, name), identity)

    def _write_trunk(self, techno, name, trunk_id, tenant_uuid):
        identity = EndpointIdentity(TRUNK, trunk_id, tenant_uuid)
        self._identity_map.write((techno, name), identity)
        # a trunk event can make a client URI known: read the registrations again
        self._identity_map.forget_client_uris()

    def _techno_name_from_channel(self, channel):
        techno, end = channel.split('/', 1)
        name, _ = end.rsplit('-', 1)
        return techno, name
