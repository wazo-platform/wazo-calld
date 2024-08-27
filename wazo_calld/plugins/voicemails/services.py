# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import base64

import requests
from ari.exceptions import ARIHTTPError

from wazo_calld.plugin_helpers import confd

from .exceptions import (
    InvalidVoicemailGreeting,
    NoSuchVoicemailGreeting,
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

    def get_voicemail_tenant(self, tenant_uuid, voicemail_id):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        return self._storage.get_voicemail_info(vm_conf)

    def get_user_voicemail(self, user_uuid):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._storage.get_voicemail_info(vm_conf)

    def get_folder(self, voicemail_id, folder_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._storage.get_folder_info(vm_conf, folder_id)

    def get_folder_tenant(self, tenant_uuid, voicemail_id, folder_id):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        return self._storage.get_folder_info(vm_conf, folder_id)

    def get_user_folder(self, user_uuid, folder_id):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._storage.get_folder_info(vm_conf, folder_id)

    def get_message(self, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._storage.get_message_info(vm_conf, message_id)

    def get_user_message(self, user_uuid, message_id):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._storage.get_message_info(vm_conf, message_id)

    def get_message_recording(self, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._get_message_recording(vm_conf, message_id)

    def get_user_message_recording(self, user_uuid, message_id):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._get_message_recording(vm_conf, message_id)

    def _get_message_recording(self, vm_conf, message_id):
        message_info, recording = self._storage.get_message_info_and_recording(
            vm_conf, message_id
        )
        if message_info['folder'].is_unread:
            dest_folder = self._storage.get_folder_by_type(VoicemailFolderType.old)
            self._move_message(vm_conf, message_info, dest_folder)
        return recording

    def move_message(self, voicemail_id, message_id, dest_folder_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        dest_folder = self._storage.get_folder_by_id(dest_folder_id)
        message_info = self._storage.get_message_info(vm_conf, message_id)
        self._move_message(vm_conf, message_info, dest_folder)

    def move_user_message(self, user_uuid, message_id, dest_folder_id):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        dest_folder = self._storage.get_folder_by_id(dest_folder_id)
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
        return self._delete_message(vm_conf, message_id)

    def delete_user_message(self, user_uuid, message_id):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._delete_message(vm_conf, message_id)

    def _delete_message(self, vm_conf, message_id):
        message_info = self._storage.get_message_info(vm_conf, message_id)
        body = {
            'mailbox': vm_conf['number'],
            'context': vm_conf['context'],
            'folder': message_info['folder'].path.decode('utf-8'),
            'message_id': message_id,
        }
        self._ari.wazo.deleteVoicemailMessage(body=body)

    def get_greeting_tenant(self, tenant_uuid, voicemail_id, greeting):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        return self._get_greeting(vm_conf, greeting)

    def get_greeting(self, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._get_greeting(vm_conf, greeting)

    def get_user_greeting(self, user_uuid, greeting):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._get_greeting(vm_conf, greeting)

    def _get_greeting(self, vm_conf, greeting):
        try:
            return base64.b64decode(
                self._ari.wazo.getVoicemailGreeting(
                    context=vm_conf['context'],
                    voicemail=vm_conf['number'],
                    greeting=greeting,
                )['greeting_base64'].encode()
            )
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 404:
                raise NoSuchVoicemailGreeting(greeting)
            raise

    def validate_greeting_exists_tenant(self, tenant_uuid, voicemail_id, greeting):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        return self._validate_greeting_exists(vm_conf, greeting)

    def validate_greeting_exists(self, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._validate_greeting_exists(vm_conf, greeting)

    def validate_user_greeting_exists(self, user_uuid, greeting):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._validate_greeting_exists(vm_conf, greeting)

    def _validate_greeting_exists(self, vm_conf, greeting):
        try:
            self._ari.wazo.getVoicemailGreeting(
                context=vm_conf['context'],
                voicemail=vm_conf['number'],
                greeting=greeting,
            )
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 404:
                raise NoSuchVoicemailGreeting(greeting)
            raise

    def create_greeting_tenant(self, tenant_uuid, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        return self._create_greeting(vm_conf, greeting, data)

    def create_greeting(self, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._create_greeting(vm_conf, greeting, data)

    def create_user_greeting(self, user_uuid, greeting, data):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._create_greeting(vm_conf, greeting, data)

    def _create_greeting(self, vm_conf, greeting, data):
        body = {'greeting_base64': base64.b64encode(data).decode()}
        try:
            self._ari.wazo.createVoicemailGreeting(
                context=vm_conf['context'],
                voicemail=vm_conf['number'],
                greeting=greeting,
                body=body,
            )
        except requests.HTTPError as e:
            # FIXME(sileht): Why ari-py does not raise ARIHTTPError for 400 ?
            if e.response.status_code == 400:
                raise InvalidVoicemailGreeting(greeting)
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 409:
                raise VoicemailGreetingAlreadyExists(greeting)
            raise

    def update_greeting_tenant(self, tenant_uuid, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        return self._update_greeting(vm_conf, greeting, data)

    def update_greeting(self, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        return self._update_greeting(vm_conf, greeting, data)

    def update_user_greeting(self, user_uuid, greeting, data):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return self._update_greeting(vm_conf, greeting, data)

    def _update_greeting(self, vm_conf, greeting, data):
        body = {'greeting_base64': base64.b64encode(data).decode()}
        try:
            self._ari.wazo.changeVoicemailGreeting(
                context=vm_conf['context'],
                voicemail=vm_conf['number'],
                greeting=greeting,
                body=body,
            )
        except requests.HTTPError as e:
            # FIXME(sileht): Why ari-py does not raise ARIHTTPError for 400 ?
            if e.response.status_code == 400:
                raise InvalidVoicemailGreeting(greeting)
        except ARIHTTPError as e:
            if e.original_error.response.status_code == 404:
                raise NoSuchVoicemailGreeting(greeting)
            raise

    def delete_greeting_tenant(self, tenant_uuid, voicemail_id, greeting):
        vm_conf = confd.get_voicemail_tenant(
            tenant_uuid, voicemail_id, self._confd_client
        )
        self._ari.wazo.removeVoicemailGreeting(
            context=vm_conf['context'],
            voicemail=vm_conf['number'],
            greeting=greeting,
        )

    def delete_greeting(self, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        self._ari.wazo.removeVoicemailGreeting(
            context=vm_conf['context'],
            voicemail=vm_conf['number'],
            greeting=greeting,
        )

    def delete_user_greeting(self, user_uuid, greeting):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        self._ari.wazo.removeVoicemailGreeting(
            context=vm_conf['context'],
            voicemail=vm_conf['number'],
            greeting=greeting,
        )

    def copy_greeting_tenant(self, tenant_uuid, voicemail_id, greeting, dest_greeting):
        data = self.get_greeting_tenant(tenant_uuid, voicemail_id, greeting)
        try:
            self.update_greeting_tenant(tenant_uuid, voicemail_id, dest_greeting, data)
        except NoSuchVoicemailGreeting:
            self.create_greeting_tenant(tenant_uuid, voicemail_id, dest_greeting, data)

    def copy_greeting(self, voicemail_id, greeting, dest_greeting):
        data = self.get_greeting(voicemail_id, greeting)
        try:
            self.update_greeting(voicemail_id, dest_greeting, data)
        except NoSuchVoicemailGreeting:
            self.create_greeting(voicemail_id, dest_greeting, data)

    def copy_user_greeting(self, user_uuid, greeting, dest_greeting):
        data = self.get_user_greeting(user_uuid, greeting)
        try:
            self.update_user_greeting(user_uuid, dest_greeting, data)
        except NoSuchVoicemailGreeting:
            self.create_user_greeting(user_uuid, dest_greeting, data)
