# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_calld.types import PluginDependencies

from .http import SwaggerResource


class Plugin:
    def load(self, dependencies: PluginDependencies) -> None:
        api = dependencies['api']
        api.add_resource(SwaggerResource, '/api/api.yml')
