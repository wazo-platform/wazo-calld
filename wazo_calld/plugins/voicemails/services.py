# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import base64

from ari.exceptions import ARIHTTPError
import requests
from wazo_calld.helpers import confd

from .exceptions import (
    NoSuchVoicemailGreeting,
    InvalidVoicemailGreeting,
    VoicemailGreetingAlreadyExists,
)
from .storage import VoicemailFolderType


class VoicemailsService:

    def __init__(self, ari, confd_client, voicemail_storage):
        self._ari = ari
        self._confd_client = confd_client
        self._storage = voicemail_storage

    def get_voicemail(self, voicemail_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._storage.get_voicemail_info(vm_conf)

    def get_folder(self, voicemail_id, folder_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._storage.get_folder_info(vm_conf, folder_id)

    def get_message(self, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._storage.get_message_info(vm_conf, message_id)

    def get_message_recording(self, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        message_info, recording = self._storage.get_message_info_and_recording(vm_conf, message_id)
        if message_info['folder'].is_unread:
            dest_folder = self._storage.get_folder_by_type(VoicemailFolderType.old)
            self._move_message(vm_conf, message_info, dest_folder)
        return recording

    def move_message(self, voicemail_id, message_id, dest_folder_id):
        dest_folder = self._storage.get_folder_by_id(dest_folder_id)
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        message_info = self._storage.get_message_info(vm_conf, message_id)
        self._move_message(vm_conf, message_info, dest_folder)

    def _move_message(self, vm_conf, message_info, dest_folder):
        body = {
            'mailbox': vm_conf['number'],
            'context': vm_conf['context'],
            'src_folder': message_info['folder'].path.decode('utf-8'),
            'dest_folder': dest_folder.path.decode('utf-8'),
            'message_id': message_info['id'],
        }
        self._ari.wazo.moveVoicemailMessage(body=body)

    def delete_message(self, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        message_info = self._storage.get_message_info(vm_conf, message_id)
        body = {
            'mailbox': vm_conf['number'],
            'context': vm_conf['context'],
            'folder': message_info['folder'].path.decode('utf-8'),
            'message_id': message_id,
        }
        self._ari.wazo.deleteVoicemailMessage(body=body)

    def get_user_voicemail_id(self, user_uuid):
        user_voicemail_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return user_voicemail_conf['id']

    def get_greeting(self, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        try:
            return base64.b64decode(self._ari.wazo.getVoicemailGreeting(
                context=vm_conf['context'],
                voicemail=vm_conf['number'],
                greeting=greeting,
            )['greeting_base64'].encode())
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 404:
                raise NoSuchVoicemailGreeting(greeting)
            raise

    def create_greeting(self, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        body = {
            'greeting_base64': base64.b64encode(data).decode()
        }
        try:
            self._ari.wazo.createVoicemailGreeting(
                context=vm_conf['context'],
                voicemail=vm_conf['number'],
                greeting=greeting,
                body=body
            )
        except requests.HTTPError as e:
            # FIXME(sileht): Why ari-py does not raise ARIHTTPError for 400 ?
            if e.response.status_code == 400:
                raise InvalidVoicemailGreeting(greeting)
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 409:
                raise VoicemailGreetingAlreadyExists(greeting)
            raise

    def update_greeting(self, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        body = {
            'greeting_base64': base64.b64encode(data).decode()
        }
        try:
            self._ari.wazo.changeVoicemailGreeting(
                context=vm_conf['context'],
                voicemail=vm_conf['number'],
                greeting=greeting,
                body=body
            )
        except requests.HTTPError as e:
            # FIXME(sileht): Why ari-py does not raise ARIHTTPError for 400 ?
            if e.response.status_code == 400:
                raise InvalidVoicemailGreeting(greeting)
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 404:
                raise NoSuchVoicemailGreeting(greeting)
            raise

    def delete_greeting(self, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        self._ari.wazo.removeVoicemailGreeting(
            context=vm_conf['context'],
            voicemail=vm_conf['number'],
            greeting=greeting,
        )

    def copy_greeting(self, voicemail_id, greeting, dest_greeting):
        data = self.get_greeting(voicemail_id, greeting)
        try:
            self.update_greeting(voicemail_id, dest_greeting, data)
        except NoSuchVoicemailGreeting:
            self.create_greeting(voicemail_id, dest_greeting, data)
