# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import re

from flask import request
from flask import Response
from marshmallow import Schema, fields

from xivo.mallow.validate import OneOf

from wazo_calld.auth import get_token_user_uuid_from_request
from wazo_calld.auth import required_acl
from wazo_calld.auth import extract_token_id_from_query_or_header
from wazo_calld.http import AuthResource
from .exceptions import (
    InvalidVoicemailID,
    InvalidVoicemailFolderID,
    NoSuchVoicemailGreeting,
    InvalidVoicemailMessageID,
)

VALID_GREETINGS = ["unavailable", "busy", "name"]


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


class VoicemailGreetingCopySchema(Schema):
    dest_greeting = fields.String(validate=OneOf(VALID_GREETINGS))


voicemail_schema = VoicemailSchema()
voicemail_folder_schema = VoicemailFolderSchema()
voicemail_message_schema = VoicemailMessageSchema()
voicemail_message_update_schema = VoicemailMessageUpdateSchema()
voicemail_greeting_copy_schema = VoicemailGreetingCopySchema()


class _BaseVoicemailResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id):
        voicemail = self._voicemails_service.get_voicemail(voicemail_id)
        return voicemail_schema.dump(voicemail)


class VoicemailResource(_BaseVoicemailResource):

    @required_acl('calld.voicemails.{voicemail_id}.read')
    def get(self, voicemail_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        return self._get(voicemail_id)


class UserVoicemailResource(_BaseVoicemailResource):

    def __init__(self, auth_client, voicemails_service):
        super().__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('calld.users.me.voicemails.read')
    def get(self):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        return self._get(voicemail_id)


class _BaseVoicemailFolderResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id, folder_id):
        folder = self._voicemails_service.get_folder(voicemail_id, folder_id)
        return voicemail_folder_schema.dump(folder)


class VoicemailFolderResource(_BaseVoicemailFolderResource):

    @required_acl('calld.voicemails.{voicemail_id}.folders.{folder_id}.read')
    def get(self, voicemail_id, folder_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        folder_id = _validate_folder_id(folder_id)
        return self._get(voicemail_id, folder_id)


class UserVoicemailFolderResource(_BaseVoicemailFolderResource):

    def __init__(self, auth_client, voicemails_service):
        super().__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('calld.users.me.voicemails.folders.{folder_id}.read')
    def get(self, folder_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        folder_id = _validate_folder_id(folder_id)
        return self._get(voicemail_id, folder_id)


class _BaseVoicemailMessageResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get(self, voicemail_id, message_id):
        message = self._voicemails_service.get_message(voicemail_id, message_id)
        return voicemail_message_schema.dump(message)

    def _put(self, voicemail_id, message_id):
        data = voicemail_message_update_schema.load(request.get_json(force=True))
        self._voicemails_service.move_message(voicemail_id, message_id, data['folder_id'])
        return '', 204

    def _delete(self, voicemail_id, message_id):
        self._voicemails_service.delete_message(voicemail_id, message_id)
        return '', 204


class VoicemailMessageResource(_BaseVoicemailMessageResource):

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.read')
    def get(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.update')
    def put(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._put(voicemail_id, message_id)

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.delete')
    def delete(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._delete(voicemail_id, message_id)


class UserVoicemailMessageResource(_BaseVoicemailMessageResource):

    def __init__(self, auth_client, voicemails_service):
        super().__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('calld.users.me.voicemails.messages.{message_id}.read')
    def get(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)

    @required_acl('calld.users.me.voicemails.messages.{message_id}.update')
    def put(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._put(voicemail_id, message_id)

    @required_acl('calld.users.me.voicemails.messages.{message_id}.delete')
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

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.recording.read',
                  extract_token_id=extract_token_id_from_query_or_header)
    def get(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)


class UserVoicemailRecordingResource(_BaseVoicemailRecordingResource):

    def __init__(self, auth_client, voicemails_service):
        super().__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('calld.users.me.voicemails.messages.{message_id}.recording.read',
                  extract_token_id=extract_token_id_from_query_or_header)
    def get(self, message_id):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        message_id = _validate_message_id(message_id)
        return self._get(voicemail_id, message_id)


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
        return message_id
    raise InvalidVoicemailMessageID(message_id)


def _get_voicemail_id_from_request(auth_client, voicemails_service):
    user_uuid = get_token_user_uuid_from_request(auth_client)
    return voicemails_service.get_user_voicemail_id(user_uuid)


class _BaseVoicemailGreetingResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _post(self, voicemail_id, greeting):
        self._voicemails_service.create_greeting(voicemail_id, greeting,
                                                 request.data)
        return '', 204

    def _get(self, voicemail_id, greeting):
        data = self._voicemails_service.get_greeting(voicemail_id, greeting)
        headers = {'Content-Disposition':
                   'attachment;filename=vm-greeting-{}.wav'.format(greeting)}
        return Response(response=data, status=200, headers=headers, content_type='audio/wav')

    def _put(self, voicemail_id, greeting):
        self._voicemails_service.update_greeting(voicemail_id, greeting,
                                                 request.data)
        return '', 204

    def _delete(self, voicemail_id, greeting):
        self._voicemails_service.delete_greeting(voicemail_id, greeting)
        return '', 204

    def _copy(self, voicemail_id, greeting):
        dest_greeting = voicemail_greeting_copy_schema.load(
            request.get_json(force=True)
        )["dest_greeting"]
        self._voicemails_service.copy_greeting(voicemail_id, greeting, dest_greeting)
        return '', 204


class VoicemailGreetingResource(_BaseVoicemailGreetingResource):

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.create')
    def post(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        return self._post(voicemail_id, greeting)

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.read')
    def get(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        return self._get(voicemail_id, greeting)

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.update')
    def put(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        return self._put(voicemail_id, greeting)

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.delete')
    def delete(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        return self._delete(voicemail_id, greeting)


class UserVoicemailGreetingResource(_BaseVoicemailGreetingResource):

    def __init__(self, auth_client, voicemails_service):
        super().__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.create')
    def post(self, greeting):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        greeting = _validate_greeting(greeting)
        return self._post(voicemail_id, greeting)

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.read')
    def get(self, greeting):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        greeting = _validate_greeting(greeting)
        return self._get(voicemail_id, greeting)

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.update')
    def put(self, greeting):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        greeting = _validate_greeting(greeting)
        return self._put(voicemail_id, greeting)

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.delete')
    def delete(self, greeting):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        greeting = _validate_greeting(greeting)
        return self._delete(voicemail_id, greeting)


class VoicemailGreetingCopyResource(_BaseVoicemailGreetingResource):

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.copy.create')
    def post(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        return self._copy(voicemail_id, greeting)


class UserVoicemailGreetingCopyResource(_BaseVoicemailGreetingResource):

    def __init__(self, auth_client, voicemails_service):
        super().__init__(voicemails_service)
        self._auth_client = auth_client

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.copy.create')
    def post(self, greeting):
        voicemail_id = _get_voicemail_id_from_request(self._auth_client, self._voicemails_service)
        greeting = _validate_greeting(greeting)
        return self._copy(voicemail_id, greeting)


def _validate_greeting(greeting):
    if greeting in VALID_GREETINGS:
        return greeting
    raise NoSuchVoicemailGreeting(greeting)
