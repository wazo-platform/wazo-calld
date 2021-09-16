# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import get_token_user_uuid_from_request
from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schemas import participant_schema


class MeetingParticipantsResource(AuthResource):

    def __init__(self, meetings_service):
        self._service = meetings_service

    @required_acl('calld.meetings.{meeting_uuid}.participants.read')
    def get(self, meeting_uuid):
        tenant = Tenant.autodetect()
        participants = self._service.list_participants(tenant.uuid, meeting_uuid)
        items = {
            'items': participant_schema.dump(participants, many=True),
            'total': len(participants),
        }
        return items, 200


class MeetingParticipantsUserResource(AuthResource):

    def __init__(self, auth_client, meetings_service):
        self._auth_client = auth_client
        self._service = meetings_service

    @required_acl('calld.users.me.meetings.{meeting_uuid}.participants.read')
    def get(self, meeting_uuid):
        tenant = Tenant.autodetect()
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        participants = self._service.user_list_participants(tenant.uuid, user_uuid, meeting_uuid)
        items = {
            'items': participant_schema.dump(participants, many=True),
            'total': len(participants),
        }
        return items, 200
