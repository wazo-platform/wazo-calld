# Copyright 2021-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from jsonpatch import JsonPatch
from xivo.auth_verifier import required_acl

from wazo_calld.auth import required_master_tenant
from wazo_calld.http import AuthResource

from .schemas import config_patch_schema


class ConfigResource(AuthResource):
    def __init__(self, config_service):
        self._config_service = config_service

    @required_master_tenant()
    @required_acl('calld.config.read')
    def get(self):
        return self._config_service.get_config(), 200

    @required_master_tenant()
    @required_acl('calld.config.update')
    def patch(self):
        config_patch = config_patch_schema.load(request.get_json(), many=True)
        config = self._config_service.get_config()
        patched_config = JsonPatch(config_patch).apply(config)
        self._config_service.update_config(patched_config)
        return self._config_service.get_config(), 200
