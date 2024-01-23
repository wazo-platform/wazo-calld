# Copyright 2020-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request

from wazo_calld.auth import get_token_user_uuid_from_request, required_acl
from wazo_calld.http import AuthResource

from .schemas import adhoc_conference_creation_schema


class UserAdhocConferencesResource(AuthResource):
    def __init__(self, adhoc_conference_service):
        self._adhoc_conference_service = adhoc_conference_service

    @required_acl('calld.users.me.conferences.adhoc.create')
    def post(self):
        user_uuid = get_token_user_uuid_from_request()
        request_body = adhoc_conference_creation_schema.load(
            request.get_json(force=True)
        )

        adhoc_conference = self._adhoc_conference_service.create_from_user(
            request_body['host_call_id'],
            request_body['participant_call_ids'],
            user_uuid,
        )

        return adhoc_conference, 201


class UserAdhocConferenceResource(AuthResource):
    def __init__(self, adhoc_conference_service):
        self._adhoc_conference_service = adhoc_conference_service

    @required_acl('calld.users.me.conferences.adhoc.delete')
    def delete(self, adhoc_conference_id):
        user_uuid = get_token_user_uuid_from_request()
        self._adhoc_conference_service.delete_from_user(adhoc_conference_id, user_uuid)

        return '', 204


class UserAdhocConferenceParticipantResource(AuthResource):
    def __init__(self, adhoc_conference_service):
        self._adhoc_conference_service = adhoc_conference_service

    @required_acl('calld.users.me.conferences.adhoc.participants.update')
    def put(self, adhoc_conference_id, call_id):
        user_uuid = get_token_user_uuid_from_request()
        self._adhoc_conference_service.add_participant_from_user(
            adhoc_conference_id,
            call_id,
            user_uuid,
        )
        return '', 204

    @required_acl('calld.users.me.conferences.adhoc.participants.delete')
    def delete(self, adhoc_conference_id, call_id):
        user_uuid = get_token_user_uuid_from_request()
        self._adhoc_conference_service.remove_participant_from_user(
            adhoc_conference_id,
            call_id,
            user_uuid,
        )
        return '', 204
