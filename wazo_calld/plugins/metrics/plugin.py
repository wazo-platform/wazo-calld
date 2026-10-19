# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from xivo.flask.metrics import init_flask_metrics

from wazo_calld.types import PluginDependencies


class Plugin:
    def load(self, dependencies: PluginDependencies) -> None:
        api = dependencies['api']

        init_flask_metrics(api.app, api)
