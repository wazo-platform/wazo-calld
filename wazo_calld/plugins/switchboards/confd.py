# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.plugins.switchboards.exceptions import NoSuchSwitchboard
from requests import HTTPError
from requests import RequestException

from wazo_calld.plugin_helpers.confd import not_found
from wazo_calld.plugin_helpers.exceptions import WazoConfdUnreachable


class Switchboard:
    def __init__(self, tenant_uuid, uuid, confd_client):
        self.tenant_uuid = tenant_uuid
        self.uuid = uuid
        self._confd = confd_client

    def exists(self):
        try:
            self._get_queue()
        except NoSuchSwitchboard:
            return False
        else:
            return True

    def hold_moh(self):
        return self._get_queue()['waiting_room_music_on_hold']

    def queue_moh(self):
        return self._get_queue()['queue_music_on_hold']

    def _get_queue(self):
        try:
            return self._confd.switchboards.get(self.uuid, tenant_uuid=self.tenant_uuid)
        except HTTPError as e:
            if not_found(e):
                raise NoSuchSwitchboard(self.uuid)
            raise
        except RequestException as e:
            raise WazoConfdUnreachable(self._confd, e)
