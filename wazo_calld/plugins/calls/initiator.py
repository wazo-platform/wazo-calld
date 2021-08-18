# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.exceptions import WazoAmidError

logger = logging.getLogger(__name__)


class Initiator:
    def __init__(self, auth, amid, confd):
        self._auth = auth
        self._amid = amid
        self._confd = confd
        self._is_initialized = False

    def initiate(self):
        token = self._auth.token.new(expiration=120)['token']
        self._amid.set_token(token)
        self._confd.set_token(token)
        users = self._confd.users.list(recurse=True)['items']
        self._init_user_dnd_group_queue_member(users)
        self._is_initialized = True
        logger.debug('Initialized completed')

    def _init_user_dnd_group_queue_member(self, users):
        for user in users:
            logger.debug('Initializing user "{}" services'.format(user['uuid']))
            if not user.get('groups'):
                continue
            user_services = user.get('services') or {}
            user_dnd = user_services.get('dnd') or {}
            enabled = user_dnd.get('enabled') or False
            interface = f"Local/{user['uuid']}@usersharedlines"
            try:
                if enabled:
                    ami.pause_queue_member(self._amid, interface)
                else:
                    ami.unpause_queue_member(self._amid, interface)
            except WazoAmidError as e:
                logger.warning(e)
