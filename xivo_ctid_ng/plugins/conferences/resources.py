# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo.tenant_flask_helpers import Tenant

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource

from .schemas import participant_schema


class ParticipantsResource(AuthResource):

    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl('ctid-ng.conferences.{conference_id}.participants.read')
    def get(self, conference_id):
        tenant = Tenant.autodetect()
        participants = self._service.list_participants(conference_id, tenant.uuid)
        items = {
            'items': participant_schema.dump(participants, many=True).data,
            'total': len(participants),
        }
        return items, 200


class ParticipantResource(AuthResource):

    def __init__(self, conferences_service):
        self._service = conferences_service

    @required_acl('ctid-ng.conferences.{conference_id}.participants.{participant_id}.delete')
    def delete(self, conference_id, participant_id):
        tenant = Tenant.autodetect()
        self._service.kick_participant(tenant.uuid, conference_id, participant_id)
        return '', 204
