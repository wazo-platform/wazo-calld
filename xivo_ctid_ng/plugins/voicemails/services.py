# -*- coding: utf-8 -*-
# Copyright 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.helpers import confd
from .storage import new_filesystem_storage
from .storage import VoicemailFolderType


class VoicemailsService(object):

    def __init__(self, ari, confd_client):
        self._ari = ari
        self._confd_client = confd_client
        self._storage = new_filesystem_storage()

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
        if message_info[u'folder'].is_unread:
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
            u'mailbox': vm_conf[u'number'],
            u'context': vm_conf[u'context'],
            u'src_folder': message_info[u'folder'].path,
            u'dest_folder': dest_folder.path,
            u'message_id': message_info[u'id'],
        }
        self._ari.xivo.moveVoicemailMessage(body=body)

    def delete_message(self, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(voicemail_id, self._confd_client)
        message_info = self._storage.get_message_info(vm_conf, message_id)
        body = {
            u'mailbox': vm_conf[u'number'],
            u'context': vm_conf[u'context'],
            u'folder': message_info[u'folder'].path,
            u'message_id': message_id,
        }
        self._ari.xivo.deleteVoicemailMessage(body=body)

    def get_user_voicemail_id(self, user_uuid):
        user_voicemail_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        return user_voicemail_conf[u'voicemail_id']
