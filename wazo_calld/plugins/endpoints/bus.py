# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    def subscribe(self, consumer):
        consumer.on_ami_event('PeerStatus', self.on_peer_status)

    def on_peer_status(self, event):
        logger.debug('%s', event)
        techno, name = event['Peer'].split('/', 1)
        status = event['PeerStatus']

        kwargs = {}
        if techno == 'PJSIP' and status == 'Reachable':
            kwargs['registered'] = True
        elif techno == 'PJSIP' and status == 'Unreachable':
            kwargs['registered'] = False

        self._endpoints_service.update_endpoint(techno, name, **kwargs)
