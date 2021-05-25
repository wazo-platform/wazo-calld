# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import ConfigResource
from .service import ConfigService


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']
        config_service = ConfigService(config)
        api.add_resource(
            ConfigResource, '/config', resource_class_args=[config_service]
        )
