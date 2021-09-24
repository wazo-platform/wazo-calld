# Copyright 2016-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import re

from flask import request
from flask import Response

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
from .schemas import (
    VALID_GREETINGS,
    voicemail_schema,
    voicemail_folder_schema,
    voicemail_message_schema,
    voicemail_message_update_schema,
    voicemail_greeting_copy_schema,
)


class VoicemailResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    @required_acl('calld.voicemails.{voicemail_id}.read')
    def get(self, voicemail_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        voicemail = self._voicemails_service.get_voicemail(voicemail_id)
        return voicemail_schema.dump(voicemail)


class UserVoicemailResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    @required_acl('calld.users.me.voicemails.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request()
        voicemail = self._voicemails_service.get_user_voicemail(user_uuid)
        return voicemail_schema.dump(voicemail)


class VoicemailFolderResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    @required_acl('calld.voicemails.{voicemail_id}.folders.{folder_id}.read')
    def get(self, voicemail_id, folder_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        folder_id = _validate_folder_id(folder_id)
        folder = self._voicemails_service.get_folder(voicemail_id, folder_id)
        return voicemail_folder_schema.dump(folder)


class UserVoicemailFolderResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    @required_acl('calld.users.me.voicemails.folders.{folder_id}.read')
    def get(self, folder_id):
        user_uuid = get_token_user_uuid_from_request()
        folder_id = _validate_folder_id(folder_id)
        folder = self._voicemails_service.get_user_folder(user_uuid, folder_id)
        return voicemail_folder_schema.dump(folder)


class VoicemailMessageResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.read')
    def get(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        message = self._voicemails_service.get_message(voicemail_id, message_id)
        return voicemail_message_schema.dump(message)

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.update')
    def put(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        data = voicemail_message_update_schema.load(request.get_json(force=True))
        self._voicemails_service.move_message(voicemail_id, message_id, data['folder_id'])
        return '', 204

    @required_acl('calld.voicemails.{voicemail_id}.messages.{message_id}.delete')
    def delete(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        self._voicemails_service.delete_message(voicemail_id, message_id)
        return '', 204


class UserVoicemailMessageResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    @required_acl('calld.users.me.voicemails.messages.{message_id}.read')
    def get(self, message_id):
        user_uuid = get_token_user_uuid_from_request()
        message_id = _validate_message_id(message_id)
        message = self._voicemails_service.get_user_message(user_uuid, message_id)
        return voicemail_message_schema.dump(message)

    @required_acl('calld.users.me.voicemails.messages.{message_id}.update')
    def put(self, message_id):
        user_uuid = get_token_user_uuid_from_request()
        message_id = _validate_message_id(message_id)
        data = voicemail_message_update_schema.load(request.get_json(force=True))
        self._voicemails_service.move_user_message(user_uuid, message_id, data['folder_id'])
        return '', 204

    @required_acl('calld.users.me.voicemails.messages.{message_id}.delete')
    def delete(self, message_id):
        user_uuid = get_token_user_uuid_from_request()
        message_id = _validate_message_id(message_id)
        self._voicemails_service.delete_user_message(user_uuid, message_id)
        return '', 204


class _BaseVoicemailRecordingResource(AuthResource):

    def __init__(self, voicemails_service):
        self._voicemails_service = voicemails_service

    def _get_response(self, recording, message_id):
        if request.args.get('download') == '1':
            headers = {'Content-Disposition': 'attachment;filename=vm-msg-{}.wav'.format(message_id)}
        else:
            headers = None
        return Response(response=recording, status=200, headers=headers, content_type='audio/wav')


class VoicemailRecordingResource(_BaseVoicemailRecordingResource):

    @required_acl(
        'calld.voicemails.{voicemail_id}.messages.{message_id}.recording.read',
        extract_token_id=extract_token_id_from_query_or_header,
    )
    def get(self, voicemail_id, message_id):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        message_id = _validate_message_id(message_id)
        recording = self._voicemails_service.get_message_recording(voicemail_id, message_id)
        return self._get_response(recording, message_id)


class UserVoicemailRecordingResource(_BaseVoicemailRecordingResource):

    @required_acl(
        'calld.users.me.voicemails.messages.{message_id}.recording.read',
        extract_token_id=extract_token_id_from_query_or_header,
    )
    def get(self, message_id):
        user_uuid = get_token_user_uuid_from_request()
        message_id = _validate_message_id(message_id)
        recording = self._voicemails_service.get_user_message_recording(user_uuid, message_id)
        return self._get_response(recording, message_id)


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


class VoicemailGreetingResource(AuthResource):

    content_dispo_tpl = 'attachment;filename=vm-greeting-{}.wav'

    def __init__(self, voicemails_service):
        self._service = voicemails_service

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.create')
    def post(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        self._service.create_greeting(voicemail_id, greeting, request.data)
        return '', 204

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.read')
    def head(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        self._service.validate_greeting_exists(voicemail_id, greeting)
        return '', 200

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.read')
    def get(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        data = self._service.get_greeting(voicemail_id, greeting)
        headers = {'Content-Disposition': self.content_dispo_tpl.format(greeting)}
        return Response(response=data, status=200, headers=headers, content_type='audio/wav')

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.update')
    def put(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        self._service.update_greeting(voicemail_id, greeting, request.data)
        return '', 204

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.delete')
    def delete(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        self._service.delete_greeting(voicemail_id, greeting)
        return '', 204


class UserVoicemailGreetingResource(AuthResource):

    content_dispo_tpl = 'attachment;filename=vm-greeting-{}.wav'

    def __init__(self, voicemails_service):
        self._service = voicemails_service

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.create')
    def post(self, greeting):
        user_uuid = get_token_user_uuid_from_request()
        greeting = _validate_greeting(greeting)
        self._service.create_user_greeting(user_uuid, greeting, request.data)
        return '', 204

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.read')
    def head(self, greeting):
        user_uuid = get_token_user_uuid_from_request()
        greeting = _validate_greeting(greeting)
        self._service.validate_user_greeting_exists(user_uuid, greeting)
        return '', 200

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.read')
    def get(self, greeting):
        user_uuid = get_token_user_uuid_from_request()
        greeting = _validate_greeting(greeting)
        data = self._service.get_user_greeting(user_uuid, greeting)
        headers = {'Content-Disposition': self.content_dispo_tpl.format(greeting)}
        return Response(response=data, status=200, headers=headers, content_type='audio/wav')

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.update')
    def put(self, greeting):
        user_uuid = get_token_user_uuid_from_request()
        greeting = _validate_greeting(greeting)
        self._service.update_user_greeting(user_uuid, greeting, request.data)
        return '', 204

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.delete')
    def delete(self, greeting):
        user_uuid = get_token_user_uuid_from_request()
        greeting = _validate_greeting(greeting)
        self._service.delete_user_greeting(user_uuid, greeting)
        return '', 204


class VoicemailGreetingCopyResource(AuthResource):

    def __init__(self, voicemails_service):
        self._service = voicemails_service

    @required_acl('calld.voicemails.{voicemail_id}.greetings.{greeting}.copy.create')
    def post(self, voicemail_id, greeting):
        voicemail_id = _validate_voicemail_id(voicemail_id)
        greeting = _validate_greeting(greeting)
        params = request.get_json(force=True)
        greeting_form = voicemail_greeting_copy_schema.load(params)
        dest_greeting = greeting_form['dest_greeting']
        self._service.copy_greeting(voicemail_id, greeting, dest_greeting)
        return '', 204


class UserVoicemailGreetingCopyResource(AuthResource):

    def __init__(self, voicemails_service):
        self._service = voicemails_service

    @required_acl('calld.users.me.voicemails.greetings.{greeting}.copy.create')
    def post(self, greeting):
        user_uuid = get_token_user_uuid_from_request()
        greeting = _validate_greeting(greeting)
        params = request.get_json(force=True)
        greeting_form = voicemail_greeting_copy_schema.load(params)
        dest_greeting = greeting_form['dest_greeting']
        self._service.copy_user_greeting(user_uuid, greeting, dest_greeting)
        return '', 204


def _validate_greeting(greeting):
    if greeting in VALID_GREETINGS:
        return greeting
    raise NoSuchVoicemailGreeting(greeting)
