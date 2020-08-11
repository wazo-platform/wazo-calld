# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource


class UserAdhocConferencesResource(AuthResource):

    @required_acl('calld.users.me.conferences.adhoc.create')
    def post(self):
        return '', 201
