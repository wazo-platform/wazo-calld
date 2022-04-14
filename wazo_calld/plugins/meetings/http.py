# Copyright 2021-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import get_token_user_uuid_from_request
from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource, ErrorCatchingResource

from .schemas import participant_schema, status_schema


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


class MeetingParticipantItemResource(AuthResource):
    def __init__(self, meetings_service):
        self._service = meetings_service

    @required_acl('calld.meetings.{meeting_uuid}.participants.delete')
    def delete(self, meeting_uuid, participant_id):
        tenant = Tenant.autodetect()
        self._service.kick_participant(tenant.uuid, meeting_uuid, participant_id)
        return '', 204


class MeetingParticipantsUserResource(AuthResource):
    def __init__(self, meetings_service):
        self._service = meetings_service

    @required_acl('calld.users.me.meetings.{meeting_uuid}.participants.read')
    def get(self, meeting_uuid):
        tenant = Tenant.autodetect()
        user_uuid = get_token_user_uuid_from_request()
        participants = self._service.user_list_participants(
            tenant.uuid, user_uuid, meeting_uuid
        )
        items = {
            'items': participant_schema.dump(participants, many=True),
            'total': len(participants),
        }
        return items, 200


class MeetingParticipantItemUserResource(AuthResource):
    def __init__(self, meetings_service):
        self._service = meetings_service

    @required_acl('calld.users.me.meetings.participants.delete')
    def delete(self, meeting_uuid, participant_id):
        tenant = Tenant.autodetect()
        user_uuid = get_token_user_uuid_from_request()
        self._service.user_kick_participant(tenant.uuid, user_uuid, meeting_uuid, participant_id)
        return '', 204


class MeetingStatusGuestResource(ErrorCatchingResource):
    def __init__(self, meetings_service):
        self._service = meetings_service

    def get(self, meeting_uuid):
        status = self._service.get_status(meeting_uuid)
        return status_schema.dump(status)
