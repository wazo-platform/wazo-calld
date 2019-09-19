# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from requests import HTTPError
from requests import RequestException

from wazo_calld.exceptions import WazoConfdUnreachable
from wazo_calld.helpers.confd import not_found


class Switchboard:
    def __init__(self, tenant_uuid, uuid, confd_client):
        self.tenant_uuid = tenant_uuid
        self.uuid = uuid
        self._confd = confd_client

    def exists(self):
        try:
            self._confd.switchboards.get(self.uuid, tenant_uuid=self.tenant_uuid)
        except HTTPError as e:
            if not_found(e):
                return False
            raise
        except RequestException as e:
            raise WazoConfdUnreachable(self._confd, e)
        else:
            return True
