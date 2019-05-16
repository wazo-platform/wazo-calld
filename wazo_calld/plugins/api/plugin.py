# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


from .resources import SwaggerResource


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(SwaggerResource, '/api/api.yml')
