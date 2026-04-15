# Copyright 2016-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import logging
from datetime import datetime
from typing import Literal

import requests
from ari.exceptions import ARIHTTPError

from wazo_calld.plugin_helpers import confd
from wazo_calld.plugin_helpers.exceptions import NoSuchUserVoicemail

from .exceptions import (
    InvalidVoicemailGreeting,
    NoSuchVoicemailGreeting,
    NoSuchVoicemailMessage,
    VoicemailGreetingAlreadyExists,
)

logger = logging.getLogger(__name__)

VoicemailTypes = Literal["all", "global", "personal"]


class VoicemailsService:
    def __init__(self, ari, confd_client, voicemail_storage, call_logd_client):
        self._ari = ari
        self._confd_client = confd_client
        self._storage = voicemail_storage
        self._call_logd_client = call_logd_client

    def count_user_messages(
        self,
        tenant_uuid,
        user_uuid,
        voicemail_type: Literal["all", "global", "personal"] = "all",
    ):
        vm_confs = self._get_voicemails_configs(tenant_uuid, user_uuid, voicemail_type)
        if not vm_confs:
            return 0
        return self._storage.count_all_messages(*vm_confs)

    def _get_voicemails_configs(
        self, tenant_uuid, user_uuid, voicemail_type: VoicemailTypes = "all"
    ):
        vm_confs = []
        client = self._confd_client

        if voicemail_type in ("all", "personal"):
            try:
                vm_confs.append(confd.get_user_voicemail(user_uuid, client))
            except NoSuchUserVoicemail:
                pass

        if voicemail_type in ("all", "global"):
            vm_confs.extend(confd.get_global_voicemails(tenant_uuid, client))

        return vm_confs

    def get_voicemail(self, tenant_uuid, voicemail_id):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
        voicemail = self._storage.get_voicemail_info(vm_conf)
        messages = [m for f in voicemail['folders'] for m in f['messages']]
        self._enrich_messages_with_transcriptions(messages, {voicemail_id})
        return voicemail

    def get_user_voicemail(self, user_uuid):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        voicemail = self._storage.get_voicemail_info(vm_conf)
        messages = [m for f in voicemail['folders'] for m in f['messages']]
        self._enrich_messages_with_transcriptions(messages, {vm_conf['id']})
        return voicemail

    def get_folder(self, tenant_uuid, voicemail_id, folder_id):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
        folder = self._storage.get_folder_info(vm_conf, folder_id)
        self._enrich_messages_with_transcriptions(folder['messages'], {voicemail_id})
        return folder

    def get_user_folder(self, user_uuid, folder_id):
        vm_conf = confd.get_user_voicemail(user_uuid, self._confd_client)
        folder = self._storage.get_folder_info(vm_conf, folder_id)
        self._enrich_messages_with_transcriptions(folder['messages'], {vm_conf['id']})
        return folder

    def get_message(self, tenant_uuid, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
        message = self._storage.get_message_info(message_id, vm_conf)
        self._enrich_messages_with_transcriptions([message], {voicemail_id})
        return message

    def get_user_message(self, tenant_uuid, user_uuid, message_id):
        vm_confs = self._get_voicemails_configs(tenant_uuid, user_uuid, 'all')
        message = self._storage.get_message_info(message_id, *vm_confs)
        voicemail_ids = {vm_conf['id'] for vm_conf in vm_confs if 'id' in vm_conf}
        self._enrich_messages_with_transcriptions([message], voicemail_ids)
        return message

    def get_message_recording(self, tenant_uuid, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
        return self._get_message_recording(message_id, vm_conf)

    def get_user_message_recording(self, tenant_uuid, user_uuid, message_id):
        vm_confs = self._get_voicemails_configs(tenant_uuid, user_uuid, 'all')
        return self._get_message_recording(message_id, *vm_confs)

    def _get_message_recording(self, message_id, *vm_confs):
        _, recording = self._storage.get_message_info_and_recording(
            message_id, *vm_confs
        )
        return recording

    def list_user_messages(
        self,
        tenant_uuid,
        user_uuid,
        voicemail_type: Literal["all", "global", "personal"] = "all",
        limit: int | None = None,
        offset: int | None = None,
        direction: str | None = None,
        order: str | None = None,
    ):
        vm_confs = self._get_voicemails_configs(tenant_uuid, user_uuid, voicemail_type)
        if not vm_confs:
            return []

        messages = self._storage.list_messages_infos(
            *vm_confs, limit=limit, offset=offset, order=order, direction=direction
        )
        voicemail_ids = {vm_conf['id'] for vm_conf in vm_confs if 'id' in vm_conf}
        self._enrich_messages_with_transcriptions(messages, voicemail_ids)
        return messages

    def _get_tenant_voicemails_configs(
        self,
        tenant_uuid: str,
        voicemail_type: VoicemailTypes = "all",
        user_uuid: str | None = None,
        voicemail_id: int | None = None,
        recurse: bool = False,
    ) -> list[dict]:
        client = self._confd_client

        if voicemail_id is not None:
            return [confd.get_voicemail(tenant_uuid, voicemail_id, client)]

        if user_uuid is not None:
            return self._get_voicemails_configs(tenant_uuid, user_uuid, voicemail_type)

        if voicemail_type == "global":
            return confd.get_global_voicemails(tenant_uuid, client, recurse=recurse)
        elif voicemail_type == "personal":
            all_vms = confd.get_all_voicemails(tenant_uuid, client, recurse=recurse)
            return [vm for vm in all_vms if vm.get('accesstype') != 'global']
        else:
            return confd.get_all_voicemails(tenant_uuid, client, recurse=recurse)

    def count_messages(
        self,
        tenant_uuid: str,
        voicemail_type: VoicemailTypes = "all",
        user_uuid: str | None = None,
        voicemail_id: int | None = None,
        recurse: bool = False,
    ) -> int:
        vm_confs = self._get_tenant_voicemails_configs(
            tenant_uuid, voicemail_type, user_uuid, voicemail_id, recurse
        )
        if not vm_confs:
            return 0
        return self._storage.count_all_messages(*vm_confs)

    def count_filtered_messages(
        self,
        tenant_uuid: str,
        voicemail_type: VoicemailTypes = "all",
        user_uuid: str | None = None,
        voicemail_id: int | None = None,
        from_: datetime | None = None,
        until: datetime | None = None,
        recurse: bool = False,
    ) -> int | None:
        if from_ is None and until is None:
            return None
        vm_confs = self._get_tenant_voicemails_configs(
            tenant_uuid, voicemail_type, user_uuid, voicemail_id, recurse
        )
        if not vm_confs:
            return 0
        messages = self._storage.list_messages_infos(*vm_confs)
        return len(self._filter_by_timestamp(messages, from_, until))

    def list_messages(
        self,
        tenant_uuid: str,
        voicemail_type: VoicemailTypes = "all",
        user_uuid: str | None = None,
        voicemail_id: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
        direction: str | None = None,
        order: str | None = None,
        from_: datetime | None = None,
        until: datetime | None = None,
        recurse: bool = False,
    ) -> list[dict]:
        vm_confs = self._get_tenant_voicemails_configs(
            tenant_uuid, voicemail_type, user_uuid, voicemail_id, recurse
        )
        if not vm_confs:
            return []

        if from_ is not None or until is not None:
            all_messages = self._storage.list_messages_infos(
                *vm_confs, order=order, direction=direction
            )
            filtered = self._filter_by_timestamp(all_messages, from_, until)
            start = offset or 0
            end = (start + limit) if limit is not None else None
            messages = filtered[start:end]
        else:
            messages = self._storage.list_messages_infos(
                *vm_confs,
                limit=limit,
                offset=offset,
                order=order,
                direction=direction,
            )

        voicemail_ids = {vm_conf['id'] for vm_conf in vm_confs if 'id' in vm_conf}
        self._enrich_messages_with_transcriptions(messages, voicemail_ids)
        return messages

    @staticmethod
    def _filter_by_timestamp(
        messages: list[dict],
        from_: datetime | None,
        until: datetime | None,
    ) -> list[dict]:
        result = messages
        if from_ is not None:
            from_ts = int(from_.timestamp())
            result = [m for m in result if m.get('timestamp', 0) >= from_ts]
        if until is not None:
            until_ts = int(until.timestamp())
            result = [m for m in result if m.get('timestamp', 0) < until_ts]
        return result

    def _enrich_messages_with_transcriptions(self, messages, voicemail_ids):
        if not messages or not voicemail_ids:
            return
        try:
            response = (
                self._call_logd_client.voicemail_transcription.list_transcriptions(
                    voicemail_id=','.join(str(v) for v in voicemail_ids),
                )
            )
        except Exception as ex:
            logger.warning(
                'Could not fetch voicemail transcriptions from call-logd: %s', str(ex)
            )
            return
        transcriptions_by_message_id = {
            t['message_id']: t for t in response.get('items', [])
        }

        for message in messages:
            message_id = message.get('id')
            if message_id and message_id in transcriptions_by_message_id:
                t = transcriptions_by_message_id[message_id]
                message['transcription'] = {
                    'text': t['transcription_text'],
                }

    def move_message(self, tenant_uuid, voicemail_id, message_id, dest_folder_id):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
        dest_folder = self._storage.get_folder_by_id(dest_folder_id)
        message_info = self._storage.get_message_info(message_id, vm_conf)
        self._move_message(vm_conf, message_info, dest_folder)

    def move_user_message(self, tenant_uuid, user_uuid, message_id, dest_folder_id):
        dest_folder = self._storage.get_folder_by_id(dest_folder_id)
        for vm_conf in self._get_voicemails_configs(tenant_uuid, user_uuid, 'all'):
            try:
                message_info = self._storage.get_message_info(message_id, vm_conf)
            except NoSuchVoicemailMessage:
                continue
            else:
                return self._move_message(vm_conf, message_info, dest_folder)

        raise NoSuchVoicemailMessage(message_id)

    def _move_message(self, vm_conf, message_info, dest_folder):
        body = {
            'mailbox': vm_conf['number'],
            'context': vm_conf['context'],
            'src_folder': message_info['folder'].path.decode('utf-8'),
            'dest_folder': dest_folder.path.decode('utf-8'),
            'message_id': message_info['id'],
        }
        self._ari.wazo.moveVoicemailMessage(body=body)

    def delete_message(self, tenant_uuid, voicemail_id, message_id):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
        return self._delete_message(vm_conf, message_id)

    def delete_user_message(self, tenant_uuid, user_uuid, message_id):
        for vm_conf in self._get_voicemails_configs(tenant_uuid, user_uuid, 'all'):
            try:
                return self._delete_message(vm_conf, message_id)
            except NoSuchVoicemailMessage:
                continue

        raise NoSuchVoicemailMessage(message_id)

    def _delete_message(self, vm_conf, message_id):
        message_info = self._storage.get_message_info(message_id, vm_conf)
        body = {
            'mailbox': vm_conf['number'],
            'context': vm_conf['context'],
            'folder': message_info['folder'].path.decode('utf-8'),
            'message_id': message_id,
        }
        self._ari.wazo.deleteVoicemailMessage(body=body)

    def get_greeting(self, tenant_uuid, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
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

    def validate_greeting_exists(self, tenant_uuid, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
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

    def create_greeting(self, tenant_uuid, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
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

    def update_greeting(self, tenant_uuid, voicemail_id, greeting, data):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
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

    def delete_greeting(self, tenant_uuid, voicemail_id, greeting):
        vm_conf = confd.get_voicemail(tenant_uuid, voicemail_id, self._confd_client)
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

    def copy_greeting(self, tenant_uuid, voicemail_id, greeting, dest_greeting):
        data = self.get_greeting(tenant_uuid, voicemail_id, greeting)
        try:
            self.update_greeting(tenant_uuid, voicemail_id, dest_greeting, data)
        except NoSuchVoicemailGreeting:
            self.create_greeting(tenant_uuid, voicemail_id, dest_greeting, data)

    def copy_user_greeting(self, user_uuid, greeting, dest_greeting):
        data = self.get_user_greeting(user_uuid, greeting)
        try:
            self.update_user_greeting(user_uuid, dest_greeting, data)
        except NoSuchVoicemailGreeting:
            self.create_user_greeting(user_uuid, dest_greeting, data)
