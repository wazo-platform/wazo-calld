# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import get_token_user_uuid_from_request
from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schemas import participant_schema


class ParticipantsResource(AuthResource):
    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl('calld.conferences.{conference_id}.participants.read')
    def get(self, conference_id):
        tenant = Tenant.autodetect()
        participants = self._service.list_participants(tenant.uuid, conference_id)
        items = {
            'items': participant_schema.dump(participants, many=True),
            'total': len(participants),
        }
        return items, 200


class ParticipantsUserResource(AuthResource):
    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl('calld.users.me.conferences.{conference_id}.participants.read')
    def get(self, conference_id):
        tenant = Tenant.autodetect()
        user_uuid = get_token_user_uuid_from_request()
        participants = self._service.user_list_participants(
            tenant.uuid, user_uuid, conference_id
        )
        items = {
            'items': participant_schema.dump(participants, many=True),
            'total': len(participants),
        }
        return items, 200


class ParticipantResource(AuthResource):
    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl(
        'calld.conferences.{conference_id}.participants.{participant_id}.delete'
    )
    def delete(self, conference_id, participant_id):
        tenant = Tenant.autodetect()
        self._service.kick_participant(tenant.uuid, conference_id, participant_id)
        return '', 204


class ParticipantMuteResource(AuthResource):
    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl(
        'calld.conferences.{conference_id}.participants.{participant_id}.mute.update'
    )
    def put(self, conference_id, participant_id):
        tenant = Tenant.autodetect()
        self._service.mute_participant(tenant.uuid, conference_id, participant_id)
        return '', 204


class ParticipantUnmuteResource(AuthResource):
    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl(
        'calld.conferences.{conference_id}.participants.{participant_id}.unmute.update'
    )
    def put(self, conference_id, participant_id):
        tenant = Tenant.autodetect()
        self._service.unmute_participant(tenant.uuid, conference_id, participant_id)
        return '', 204


class ConferenceRecordResource(AuthResource):
    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl('calld.conferences.{conference_id}.record.create')
    def post(self, conference_id):
        tenant = Tenant.autodetect()
        self._service.record(tenant.uuid, conference_id)
        return '', 204

    @required_acl('calld.conferences.{conference_id}.record.delete')
    def delete(self, conference_id):
        tenant = Tenant.autodetect()
        self._service.stop_record(tenant.uuid, conference_id)
        return '', 204
