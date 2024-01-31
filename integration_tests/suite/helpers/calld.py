# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import time
import uuid
from contextlib import contextmanager

import requests
from hamcrest import assert_that, equal_to
from wazo_calld_client import Client

from .constants import VALID_TOKEN

MISSING = object()


class CalldClient(Client):
    def is_up(self):
        try:
            self.status.get()
        except requests.HTTPError:
            return True
        except requests.RequestException:
            return False
        return True

    @contextmanager
    def calls_send_no_content_type(self):
        def no_json(decorated):
            def decorator(*args, **kwargs):
                kwargs['data'] = json.dumps(kwargs.pop('json'))
                return decorated(*args, **kwargs)

            return decorator

        old_post = self.calls.session.post
        old_put = self.calls.session.put
        self.calls.session.post = no_json(self.calls.session.post)
        self.calls.session.put = no_json(self.calls.session.put)
        yield
        self.calls.session.post = old_post
        self.calls.session.put = old_put


class LegacyCalldClient:
    _url_tpl = 'http://{host}:{port}/1.0/{path}'

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        path = '/'.join(str(part) for part in parts)
        return self._url_tpl.format(host=self._host, port=self._port, path=path)

    def post_user_me_call_result(self, body, token=None):
        url = self.url('users', 'me', 'calls')
        result = requests.post(url, json=body, headers=self._headers(token=token))
        return result

    def originate_me(
        self,
        extension,
        variables=None,
        line_id=None,
        from_mobile=False,
        all_lines=False,
        auto_answer_caller=False,
        token=VALID_TOKEN,
    ):
        body = {'extension': extension}
        if variables:
            body['variables'] = variables
        if line_id:
            body['line_id'] = line_id
        if from_mobile:
            body['from_mobile'] = from_mobile
        if all_lines:
            body['all_lines'] = all_lines
        if auto_answer_caller:
            body['auto_answer_caller'] = auto_answer_caller
        response = self.post_user_me_call_result(body, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def delete_call_result(self, call_id, token=None):
        url = self.url('calls', call_id)
        result = requests.delete(url, headers=self._headers(token=token))
        return result

    def hangup_call(self, call_id, token=VALID_TOKEN):
        response = self.delete_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def delete_user_me_call_result(self, call_id, token=None):
        url = self.url('users', 'me', 'calls', call_id)
        result = requests.delete(url, headers=self._headers(token=token))
        return result

    def hangup_my_call(self, call_id, token=VALID_TOKEN):
        response = self.delete_user_me_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def put_call_user_result(self, call_id, user_uuid, token, timeout=MISSING):
        url = self.url('calls', call_id, 'user', user_uuid)
        body = {}
        if timeout is not MISSING:
            body['timeout'] = timeout
        params = {'json': body} if body else {}
        result = requests.put(url, headers=self._headers(token=token), **params)
        return result

    def connect_user(self, call_id, user_uuid, timeout=MISSING):
        response = self.put_call_user_result(
            call_id, user_uuid, token=VALID_TOKEN, timeout=timeout
        )
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_users_me_transfers_result(self, token=None):
        url = self.url('users', 'me', 'transfers')
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def list_my_transfers(self, token=VALID_TOKEN):
        response = self.get_users_me_transfers_result(token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def post_transfer_result(self, body, token=None):
        url = self.url('transfers')
        result = requests.post(url, json=body, headers=self._headers(token=token))
        return result

    def create_transfer(
        self,
        transferred_call,
        initiator_call,
        context,
        exten,
        variables=None,
        timeout=None,
    ):
        body = {
            'transferred_call': transferred_call,
            'initiator_call': initiator_call,
            'context': context,
            'exten': exten,
            'flow': 'attended',
        }
        if variables:
            body['variables'] = variables
        if timeout:
            body['timeout'] = timeout
        response = self.post_transfer_result(body, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def create_blind_transfer(self, transferred_call, initiator_call, context, exten):
        body = {
            'transferred_call': transferred_call,
            'initiator_call': initiator_call,
            'context': context,
            'exten': exten,
            'flow': 'blind',
        }
        response = self.post_transfer_result(body, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def post_user_transfer_result(self, body, token=None):
        url = self.url('users', 'me', 'transfers')
        result = requests.post(url, json=body, headers=self._headers(token=token))
        return result

    def create_user_transfer(self, initiator_call, exten, token=VALID_TOKEN):
        body = {
            'initiator_call': initiator_call,
            'exten': exten,
            'flow': 'attended',
        }
        response = self.post_user_transfer_result(body, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def put_complete_transfer_result(self, transfer_id, token=None):
        url = self.url('transfers', transfer_id, 'complete')
        result = requests.put(url, headers=self._headers(token=token))
        return result

    def complete_transfer(self, transfer_id):
        response = self.put_complete_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(204))

    def put_users_me_complete_transfer_result(self, transfer_id, token=None):
        url = self.url('users', 'me', 'transfers', transfer_id, 'complete')
        result = requests.put(url, headers=self._headers(token=token))
        return result

    def complete_my_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.put_users_me_complete_transfer_result(transfer_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def delete_transfer_result(self, transfer_id, token=None):
        url = self.url('transfers', transfer_id)
        result = requests.delete(url, headers=self._headers(token=token))
        return result

    def cancel_transfer(self, transfer_id):
        response = self.delete_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(204))

    def delete_users_me_transfer_result(self, transfer_id, token=None):
        url = self.url('users', 'me', 'transfers', transfer_id)
        result = requests.delete(url, headers=self._headers(token=token))
        return result

    def cancel_my_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.delete_users_me_transfer_result(transfer_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def get_transfer_result(self, transfer_id, token=None):
        url = self.url('transfers', transfer_id)
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def get_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.get_transfer_result(transfer_id, token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_status_result(self, token=None):
        url = self.url('status')
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def status(self, token=VALID_TOKEN):
        response = self.get_status_result(token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_voicemail_result(self, voicemail_id, token=None):
        url = self.url('voicemails', voicemail_id)
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def get_user_me_voicemail_result(self, token=None):
        url = self.url('users', 'me', 'voicemails')
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def get_voicemail_folder_result(self, voicemail_id, folder_id, token=None):
        url = self.url('voicemails', voicemail_id, 'folders', folder_id)
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def get_user_me_voicemail_folder_result(self, folder_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'folders', folder_id)
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def delete_voicemail_message_result(self, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id)
        result = requests.delete(url, headers=self._headers(token=token))
        return result

    def delete_user_me_voicemail_message_result(self, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id)
        result = requests.delete(url, headers=self._headers(token=token))
        return result

    def get_voicemail_message_result(self, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id)
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def get_user_me_voicemail_message_result(self, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id)
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def put_voicemail_message_result(
        self, message, voicemail_id, message_id, token=None
    ):
        url = self.url('voicemails', voicemail_id, 'messages', message_id)
        result = requests.put(url, json=message, headers=self._headers(token=token))
        return result

    def put_user_me_voicemail_message_result(self, message, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id)
        result = requests.put(url, json=message, headers=self._headers(token=token))
        return result

    def get_voicemail_recording_result(self, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id, 'recording')
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def get_user_me_voicemail_recording_result(self, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id, 'recording')
        result = requests.get(url, headers=self._headers(token=token))
        return result

    def switchboard_queued_calls(
        self, switchboard_uuid, token=VALID_TOKEN, tenant_uuid=None
    ):
        response = self.get_switchboard_queued_calls_result(
            switchboard_uuid, token, tenant_uuid
        )

        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_switchboard_queued_calls_result(
        self, switchboard_uuid, token=None, tenant_uuid=None
    ):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'queued')
        headers = self._headers(token=token, tenant_uuid=tenant_uuid)
        return requests.get(url, headers=headers)

    def switchboard_answer_queued_call(
        self, switchboard_uuid, call_id, token, line_id=None
    ):
        response = self.put_switchboard_queued_call_answer_result(
            switchboard_uuid, call_id, token, line_id
        )
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def put_switchboard_queued_call_answer_result(
        self, switchboard_uuid, call_id, token=None, line_id=None
    ):
        url = self.url(
            'switchboards', switchboard_uuid, 'calls', 'queued', call_id, 'answer'
        )
        params = {'line_id': line_id} if line_id else None
        return requests.put(url, headers=self._headers(token), params=params)

    def switchboard_hold_call(self, switchboard_uuid, call_id, token=VALID_TOKEN):
        response = self.put_switchboard_held_call_result(
            switchboard_uuid, call_id, token
        )
        assert_that(response.status_code, equal_to(204))

    def put_switchboard_held_call_result(self, switchboard_uuid, call_id, token=None):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'held', call_id)
        return requests.put(url, headers=self._headers(token=token))

    def switchboard_held_calls(
        self, switchboard_uuid, token=VALID_TOKEN, tenant_uuid=None
    ):
        response = self.get_switchboard_held_calls_result(
            switchboard_uuid, token, tenant_uuid
        )

        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_switchboard_held_calls_result(
        self, switchboard_uuid, token=None, tenant_uuid=None
    ):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'held')
        headers = self._headers(token=token, tenant_uuid=tenant_uuid)
        return requests.get(url, headers=headers)

    def switchboard_answer_held_call(
        self, switchboard_uuid, call_id, token, line_id=None
    ):
        response = self.put_switchboard_held_call_answer_result(
            switchboard_uuid, call_id, token, line_id
        )
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def put_switchboard_held_call_answer_result(
        self, switchboard_uuid, call_id, token=None, line_id=None
    ):
        url = self.url(
            'switchboards', switchboard_uuid, 'calls', 'held', call_id, 'answer'
        )
        params = {'line_id': line_id} if line_id else None
        return requests.put(url, headers=self._headers(token=token), params=params)

    def _headers(self, token=None, tenant_uuid=None):
        headers = {}
        if token is not None:
            headers['X-Auth-Token'] = token
        if tenant_uuid is not None:
            headers['Wazo-Tenant'] = tenant_uuid
        return headers

    @contextmanager
    def send_no_content_type(self):
        def no_json(decorated):
            def decorator(*args, **kwargs):
                kwargs['data'] = json.dumps(kwargs.pop('json'))
                return decorated(*args, **kwargs)

            return decorator

        old_post = requests.post
        old_put = requests.put
        requests.post = no_json(requests.post)
        requests.put = no_json(requests.put)
        yield
        requests.post = old_post
        requests.put = old_put


def new_call_id(leap=0):
    return format(time.time() + leap, '.2f')


def new_uuid():
    return str(uuid.uuid4())
