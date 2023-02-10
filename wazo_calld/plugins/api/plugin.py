# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


from .http import SwaggerResource


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(SwaggerResource, '/api/api.yml')
