# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging

from flask import jsonify, request
from flask_restful import Resource
from wazo_call_logd.plugins.voicemail_transcription.notifier import (
    TranscriptionNotifier,
)
from wazo_call_logd.plugins.voicemail_transcription.service import TranscriptionService

logger = logging.getLogger(__name__)


class SetTranscriptionsResource(Resource):
    def __init__(self, service: TranscriptionService, dao):
        self._service = service
        self._dao = dao

    def post(self):
        body = request.get_json()
        transcriptions = body.get('transcriptions', [])
        tenant_uuids = {t['tenant_uuid'] for t in transcriptions if 'tenant_uuid' in t}
        if tenant_uuids:
            self._dao.tenant.create_all_uuids_if_not_exist(tenant_uuids)
        for t in transcriptions:
            self._service.create_transcription(**t)
        return '', 204


class ResetResource(Resource):
    def __init__(self, service: TranscriptionService):
        self._service = service

    def post(self):
        result = self._service.list_transcriptions()
        for item in result.get('items', []):
            self._service.delete_transcription(
                item.message_id, tenant_uuids=[item.tenant_uuid]
            )
        return '', 204


class HealthResource(Resource):
    def get(self):
        return jsonify({'status': 'ok'})


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        dao = dependencies['dao']
        bus_publisher = dependencies['bus_publisher']

        notifier = TranscriptionNotifier(bus_publisher)
        service = TranscriptionService(dao, notifier)

        api.add_resource(
            SetTranscriptionsResource,
            '/_set_transcriptions',
            resource_class_args=[service, dao],
        )
        api.add_resource(
            ResetResource,
            '/_reset',
            resource_class_args=[service],
        )
        api.add_resource(
            HealthResource,
            '/_status',
        )
