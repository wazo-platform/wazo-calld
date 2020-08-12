# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .http import (
    UserAdhocConferencesResource,
)
from .services import AdhocConferencesService


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        adhoc_conferences_service = AdhocConferencesService(ari.client)
        api.add_resource(UserAdhocConferencesResource, '/users/me/conferences/adhoc', resource_class_args=[adhoc_conferences_service])
