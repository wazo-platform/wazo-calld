# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource


class UserAdhocConferencesResource(AuthResource):

    def __init__(self, adhoc_conference_service):
        self._adhoc_conference_service = adhoc_conference_service

    @required_acl('calld.users.me.conferences.adhoc.create')
    def post(self):
        user_uuid = None
        request_body = request.get_json(force=True)
        self._adhoc_conference_service.create_from_user(
            request_body['host_call_id'],
            request_body['participant_call_ids'],
            user_uuid
        )

        return '', 201
