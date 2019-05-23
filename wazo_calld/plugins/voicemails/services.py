# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.helpers import confd
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
        return user_voicemail_conf['voicemail_id']
