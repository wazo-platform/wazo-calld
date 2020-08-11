# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import (
    UserAdhocConferencesResource,
)


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(UserAdhocConferencesResource, '/users/me/conferences/adhoc', resource_class_args=[])
