# -*- coding: utf-8 -*-
# Copyright 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

import re

from flask import request
from flask import Response
from marshmallow import Schema, fields

from xivo_ctid_ng.core.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.auth import extract_token_id_from_query_or_header
from xivo_ctid_ng.core.rest_api import AuthResource
from .exceptions import InvalidVoicemailID
from .exceptions import InvalidVoicemailFolderID
from .exceptions import InvalidVoicemailMessageID


class VoicemailMessageBaseSchema(Schema):
    id = fields.String()
    caller_id_name = fields.String()
    caller_id_num = fields.String()
    duration = fields.Integer()
    timestamp = fields.Integer()


class VoicemailFolderBaseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()


class VoicemailMessageSchema(VoicemailMessageBaseSchema):
    folder = fields.Nested(VoicemailFolderBaseSchema)


class VoicemailFolderSchema(VoicemailFolderBaseSchema):
    messages = fields.Nested(VoicemailMessageBaseSchema, many=True)


class VoicemailSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    number = fields.String()
    folders = fields.Nested(VoicemailFolderSchema, many=True)


class VoicemailMessageUpdateSchema(Schema):
    folder_id = fields.Integer(required=True)


class VoicemailListenRequestSchema(Schema):
    line_id = fields.Integer()
    user = fields.String(required=True)


class UserVoicemailListenRequestSchema(Schema):
    line_id = fields.Integer()

voicemail_schema = VoicemailSchema(strict=True)
voicemail_folder_schema = VoicemailFolderSchema(strict=True)
voicemail_message_schema = VoicemailMessageSchema(strict=True)
voicemail_message_update_schema = VoicemailMessageUpdateSchema(strict=True)
voicemail_listen_request_schema = VoicemailListenRequestSchema(strict=True)
user_voicemail_listen_request_schema = UserVoicemailListenRequestSchema(strict=True)


class _BaseVoicemailResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id):
        voicemail = self._voicemails_service.get_voicemail(voicemail_id)
        return voicemail_schema.dump(voicemail).data


class VoicemailResource(_BaseVoicemailResource):

    @required_acl('ctid-ng.voicemails.{voicemail_id}.read')
    def get(self, voicemail_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        return self._get(voicemail_id)


class UserVoicemailResource(_BaseVoicemailResource):

    def __init__(self, auth_client, voicemails_service):
        super(UserVoicemailResource, self).__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('ctid-ng.users.me.voicemails.read')
    def get(self):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        return self._get(voicemail_id)


class _BaseVoicemailFolderResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id, folder_id):
        folder = self._voicemails_service.get_folder(voicemail_id, folder_id)
        return voicemail_folder_schema.dump(folder).data


class VoicemailFolderResource(_BaseVoicemailFolderResource):

    @required_acl('ctid-ng.voicemails.{voicemail_id}.folders.{folder_id}.read')
    def get(self, voicemail_id, folder_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        folder_id = _validate_folder_id(folder_id)
        return self._get(voicemail_id, folder_id)


class UserVoicemailFolderResource(_BaseVoicemailFolderResource):

    def __init__(self, auth_client, voicemails_service):
        super(UserVoicemailFolderResource, self).__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('ctid-ng.users.me.voicemails.folders.{folder_id}.read')
    def get(self, folder_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        folder_id = _validate_folder_id(folder_id)
        return self._get(voicemail_id, folder_id)


class _BaseVoicemailMessageResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id, message_id):
        message = self._voicemails_service.get_message(voicemail_id, message_id)
        return voicemail_message_schema.dump(message).data

    def _put(self, voicemail_id, message_id):
        data = voicemail_message_update_schema.load(request.get_json(force=True)).data
        self._voicemails_service.move_message(voicemail_id, message_id, data['folder_id'])
        return '', 204

    def _delete(self, voicemail_id, message_id):
        self._voicemails_service.delete_message(voicemail_id, message_id)
        return '', 204


class VoicemailMessageResource(_BaseVoicemailMessageResource):

    @required_acl('ctid-ng.voicemails.{voicemail_id}.messages.{message_id}.read')
    def get(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)

    @required_acl('ctid-ng.voicemails.{voicemail_id}.messages.{message_id}.update')
    def put(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._put(voicemail_id, message_id)

    @required_acl('ctid-ng.voicemails.{voicemail_id}.messages.{message_id}.delete')
    def delete(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._delete(voicemail_id, message_id)


class UserVoicemailMessageResource(_BaseVoicemailMessageResource):

    def __init__(self, auth_client, voicemails_service):
        super(UserVoicemailMessageResource, self).__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('ctid-ng.users.me.voicemails.messages.{message_id}.read')
    def get(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)

    @required_acl('ctid-ng.users.me.voicemails.messages.{message_id}.update')
    def put(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._put(voicemail_id, message_id)

    @required_acl('ctid-ng.users.me.voicemails.messages.{message_id}.delete')
    def delete(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._delete(voicemail_id, message_id)


class _BaseVoicemailRecordingResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id, message_id):
        recording = self._voicemails_service.get_message_recording(voicemail_id, message_id)
        if request.args.get('download') == '1':
            headers = {'Content-Disposition': 'attachment;filename=vm-msg-{}.wav'.format(message_id)}
        else:
            headers = None
        return Response(response=recording, status=200, headers=headers, content_type='audio/wav')


class VoicemailRecordingResource(_BaseVoicemailRecordingResource):

    @required_acl('ctid-ng.voicemails.{voicemail_id}.messages.{message_id}.recording.read',
                  extract_token_id=extract_token_id_from_query_or_header)
    def get(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)


class UserVoicemailRecordingResource(_BaseVoicemailRecordingResource):

    def __init__(self, auth_client, voicemails_service):
        super(UserVoicemailRecordingResource, self).__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('ctid-ng.users.me.voicemails.messages.{message_id}.recording.read',
                  extract_token_id=extract_token_id_from_query_or_header)
    def get(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)


class _BaseVoicemailListenResource(AuthResource):

    def __init__(self, calls_service, voicemails_service):
        self._calls_service = calls_service
        self._voicemails_service = voicemails_service

    def _post(self, voicemail_id, message_id, source):
        message = self._voicemails_service.get_message(voicemail_id, message_id)
        call_request = {
            'source': source,
            'destination': {
                'context': 'voicemailplaymsg',
                'extension': 's',
                'priority': '1',
            },
            'variables': {
                'XIVO_MAILBOX': message[u'vm_conf'][u'number'],
                'XIVO_MAILBOX_CONTEXT': message[u'vm_conf'][u'context'],
                'XIVO_MAILBOX_MSG_ID': message[u'id'],
                'CONNECTEDLINE(name)': '',
                'CONNECTEDLINE(num)': 'voicemail',
            }
        }
        self._calls_service.originate(call_request)
        return '', 204


class VoicemailListenResource(_BaseVoicemailListenResource):

    @required_acl('ctid-ng.voicemails.{voicemail_id}.messages.{message_id}.listen.create')
    def post(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        source = voicemail_listen_request_schema.load(request.get_json(force=True)).data
        return self._post(voicemail_id, message_id, source)


class UserVoicemailListenResource(_BaseVoicemailListenResource):

    def __init__(self, auth_client, calls_service, voicemails_service):
        super(UserVoicemailListenResource, self).__init__(calls_service, voicemails_service)
        self._auth_client = auth_client

    @required_acl('ctid-ng.users.me.voicemails.messages.{message_id}.listen.create')
    def post(self, message_id):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        voicemail_id = self._voicemails_service.get_user_voicemail_id(user_uuid)
        message_id = _validate_message_id(message_id)
        source = user_voicemail_listen_request_schema.load(request.get_json(force=True)).data
        source['user'] = user_uuid
        return self._post(voicemail_id, message_id, source)


def _validate_voicemail_id(voicemail_id):
    try:
        n = int(voicemail_id)
        if n < 0:
            raise InvalidVoicemailID(voicemail_id)
        return n
    except ValueError:
        raise InvalidVoicemailID(voicemail_id)


def _validate_folder_id(folder_id):
    try:
        n = int(folder_id)
        if n < 0:
            raise InvalidVoicemailFolderID(folder_id)
        return n
    except ValueError:
        raise InvalidVoicemailFolderID(folder_id)


_MESSAGE_ID_REGEX = re.compile('^[-a-zA-Z0-9]+$')

def _validate_message_id(message_id):
    # the check could be more restrictive but the goal is just to make
    # sure message_id is safe to use for file system operations
    if _MESSAGE_ID_REGEX.match(message_id):
        return message_id.decode('ascii')
    raise InvalidVoicemailMessageID(message_id)


def _get_voicemail_id_from_request(auth_client, voicemails_service):
    user_uuid = get_token_user_uuid_from_request(auth_client)
    return voicemails_service.get_user_voicemail_id(user_uuid)
