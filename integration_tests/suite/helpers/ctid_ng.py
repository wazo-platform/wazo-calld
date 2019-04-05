# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import requests
import time

from contextlib import contextmanager
from hamcrest import assert_that, equal_to

from .constants import VALID_TOKEN


class CtidNgClient:

    _url_tpl = 'https://{host}:{port}/1.0/{path}'

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        path = '/'.join(str(part) for part in parts)
        return self._url_tpl.format(host=self._host, port=self._port, path=path)

    def is_up(self):
        url = self.url()
        try:
            response = requests.get(url, verify=False)
            return response.status_code == 404
        except requests.RequestException:
            return False

    def application_call_hold_start(self, application_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'hold', 'start')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def application_call_hold_stop(self, application_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'hold', 'stop')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def application_call_moh_start(self, application_uuid, call_id, moh_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'moh', moh_uuid, 'start')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def application_call_moh_stop(self, application_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'moh', 'stop')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def application_call_mute_start(self, application_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'mute', 'start')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def application_call_mute_stop(self, application_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'mute', 'stop')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def application_call_playback(self, application_uuid, call_id, body, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'playbacks')
        return requests.post(url, json=body, headers={'X-Auth-Token': token}, verify=False)

    def application_call_snoop(
            self, application_uuid, call_id, snooper_call_id, whisper=None, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id, 'snoops')
        body = {
            'whisper_mode': whisper,
            'snooping_call_id': snooper_call_id,
        }
        return requests.post(url, json=body, headers={'X-Auth-Token': token}, verify=False)

    def application_edit_snoop(self, application_uuid, snoop_uuid, whisper=None, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'snoops', snoop_uuid)
        body = {'whisper_mode': whisper}
        return requests.put(url, json=body, headers={'X-Auth-Token': token}, verify=False)

    def application_delete_snoop(self, application_uuid, snoop_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'snoops', snoop_uuid)
        return requests.delete(url, headers={'X-Auth-Token': token}, verify=False)

    def application_get_snoop(self, application_uuid, snoop_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'snoops', snoop_uuid)
        return requests.get(url, headers={'X-Auth-Token': token}, verify=False)

    def application_list_snoops(self, application_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'snoops')
        return requests.get(url, headers={'X-Auth-Token': token}, verify=False)

    def application_stop_playback(self, application_uuid, playback_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'playbacks', playback_id)
        return requests.delete(url, headers={'X-Auth-Token': token}, verify=False)

    def application_new_call(
            self,
            application_uuid,
            context,
            exten,
            token=VALID_TOKEN,
            **kwargs
    ):
        url = self.url('applications', application_uuid, 'calls')
        body = dict(context=context, exten=exten, **kwargs)
        return requests.post(url, json=body, headers={'X-Auth-Token': token}, verify=False)

    def application_new_node(self, application_uuid, calls=None, token=VALID_TOKEN):
        calls = calls or {}
        body = {'calls': [{'id': call} for call in calls]}
        url = self.url('applications', application_uuid, 'nodes')
        return requests.post(url, json=body, headers={'X-Auth-Token': token}, verify=False)

    def application_new_node_call(
            self,
            application_uuid,
            node_uuid,
            context,
            exten,
            token=VALID_TOKEN,
            **kwargs
    ):
        url = self.url('applications', application_uuid, 'nodes', node_uuid, 'calls')
        body = dict(context=context, exten=exten, **kwargs)
        return requests.post(url, json=body, headers={'X-Auth-Token': token}, verify=False)

    def application_node_add_call(self, application_uuid, node_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'nodes', node_uuid, 'calls', call_id)
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def get_application(self, application_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid)
        response = requests.get(url, headers={'X-Auth-Token': token}, verify=False)
        return response

    def get_application_calls(self, application_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls')
        response = requests.get(url, headers={'X-Auth-Token': token}, verify=False)
        return response

    def get_application_nodes(self, application_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'nodes')
        response = requests.get(url, headers={'X-Auth-Token': token}, verify=False)
        return response

    def delete_application_call(self, application_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'calls', call_id)
        return requests.delete(url, headers={'X-Auth-Token': token}, verify=False)

    def delete_application_node(self, application_uuid, node_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'nodes', node_uuid)
        return requests.delete(url, headers={'X-Auth-Token': token}, verify=False)

    def delete_application_node_call(self, application_uuid, node_uuid, call_id, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'nodes', node_uuid, 'calls', call_id)
        return requests.delete(url, headers={'X-Auth-Token': token}, verify=False)

    def get_application_node(self, application_uuid, node_uuid, token=VALID_TOKEN):
        url = self.url('applications', application_uuid, 'nodes', node_uuid)
        response = requests.get(url, headers={'X-Auth-Token': token}, verify=False)
        return response

    def get_calls_result(self, application=None, application_instance=None, token=None):
        url = self.url('calls')
        params = {}
        if application:
            params['application'] = application
            if application_instance:
                params['application_instance'] = application_instance
        result = requests.get(url,
                              params=params,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def list_calls(self, application=None, application_instance=None, token=VALID_TOKEN):
        response = self.get_calls_result(application, application_instance, token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_users_me_calls_result(self, application=None, application_instance=None, token=None):
        url = self.url('users', 'me', 'calls')
        params = {}
        if application:
            params['application'] = application
            if application_instance:
                params['application_instance'] = application_instance
        result = requests.get(url,
                              params=params,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def list_my_calls(self, application=None, application_instance=None, token=VALID_TOKEN):
        response = self.get_users_me_calls_result(application, application_instance, token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_call_result(self, call_id, token=None):
        url = self.url('calls', call_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_call(self, call_id, token=VALID_TOKEN):
        response = self.get_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def post_call_result(self, source, priority, extension, context, variables=None, line_id=None, from_mobile=False, token=None):
        body = {
            'source': {
                'user': source,
            },
            'destination': {
                'priority': priority,
                'extension': extension,
                'context': context,
            },
        }
        if variables:
            body['variables'] = variables
        if line_id:
            body['source']['line_id'] = line_id
        if from_mobile:
            body['source']['from_mobile'] = from_mobile

        return self.post_call_raw(body, token)

    def post_call_raw(self, body, token=None):
        url = self.url('calls')
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def originate(self, source, priority, extension, context, variables=None, line_id=None, from_mobile=False, token=VALID_TOKEN):
        response = self.post_call_result(source, priority, extension, context, variables, line_id, from_mobile, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def post_user_me_call_result(self, body, token=None):
        url = self.url('users', 'me', 'calls')
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def originate_me(self, extension, variables=None, line_id=None, from_mobile=False, token=VALID_TOKEN):
        body = {
            'extension': extension
        }
        if variables:
            body['variables'] = variables
        if line_id:
            body['line_id'] = line_id
        if from_mobile:
            body['from_mobile'] = from_mobile
        response = self.post_user_me_call_result(body, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def delete_call_result(self, call_id, token=None):
        url = self.url('calls', call_id)
        result = requests.delete(url,
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def hangup_call(self, call_id, token=VALID_TOKEN):
        response = self.delete_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def delete_user_me_call_result(self, call_id, token=None):
        url = self.url('users', 'me', 'calls', call_id)
        result = requests.delete(url,
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def hangup_my_call(self, call_id, token=VALID_TOKEN):
        response = self.delete_user_me_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def put_call_user_result(self, call_id, user_uuid, token):
        url = self.url('calls', call_id, 'user', user_uuid)
        result = requests.put(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def connect_user(self, call_id, user_uuid):
        response = self.put_call_user_result(call_id, user_uuid, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_users_me_transfers_result(self, token=None):
        url = self.url('users', 'me', 'transfers')
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def list_my_transfers(self, token=VALID_TOKEN):
        response = self.get_users_me_transfers_result(token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def post_transfer_result(self, body, token=None):
        url = self.url('transfers')
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def create_transfer(self, transferred_call, initiator_call, context, exten, variables=None, timeout=None):
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
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
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
        result = requests.put(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def complete_transfer(self, transfer_id):
        response = self.put_complete_transfer_result(transfer_id, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(204))

    def put_users_me_complete_transfer_result(self, transfer_id, token=None):
        url = self.url('users', 'me', 'transfers', transfer_id, 'complete')
        result = requests.put(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def complete_my_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.put_users_me_complete_transfer_result(transfer_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def delete_transfer_result(self, transfer_id, token=None):
        url = self.url('transfers', transfer_id)
        result = requests.delete(url,
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def cancel_transfer(self, transfer_id):
        response = self.delete_transfer_result(transfer_id,
                                               token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(204))

    def delete_users_me_transfer_result(self, transfer_id, token=None):
        url = self.url('users', 'me', 'transfers', transfer_id)
        result = requests.delete(url,
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def cancel_my_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.delete_users_me_transfer_result(transfer_id,
                                                        token=token)
        assert_that(response.status_code, equal_to(204))

    def get_transfer_result(self, transfer_id, token=None):
        url = self.url('transfers', transfer_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.get_transfer_result(transfer_id, token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_status_result(self, token=None):
        url = self.url('status')
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def status(self, token=VALID_TOKEN):
        response = self.get_status_result(token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_voicemail_result(self, voicemail_id, token=None):
        url = self.url('voicemails', voicemail_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_user_me_voicemail_result(self, token=None):
        url = self.url('users', 'me', 'voicemails')
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_voicemail_folder_result(self, voicemail_id, folder_id, token=None):
        url = self.url('voicemails', voicemail_id, 'folders', folder_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_user_me_voicemail_folder_result(self, folder_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'folders', folder_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def delete_voicemail_message_result(self, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id)
        result = requests.delete(url,
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def delete_user_me_voicemail_message_result(self, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id)
        result = requests.delete(url,
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def get_voicemail_message_result(self, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_user_me_voicemail_message_result(self, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id)
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def put_voicemail_message_result(self, message, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id)
        result = requests.put(url,
                              json=message,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def put_user_me_voicemail_message_result(self, message, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id)
        result = requests.put(url,
                              json=message,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_voicemail_recording_result(self, voicemail_id, message_id, token=None):
        url = self.url('voicemails', voicemail_id, 'messages', message_id, 'recording')
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_user_me_voicemail_recording_result(self, message_id, token=None):
        url = self.url('users', 'me', 'voicemails', 'messages', message_id, 'recording')
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def switchboard_queued_calls(self, switchboard_uuid, token=VALID_TOKEN):
        response = self.get_switchboard_queued_calls_result(switchboard_uuid, token)

        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_switchboard_queued_calls_result(self, switchboard_uuid, token=None):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'queued')
        return requests.get(url, headers={'X-Auth-Token': token}, verify=False)

    def switchboard_answer_queued_call(self, switchboard_uuid, call_id, token):
        response = self.put_switchboard_queued_call_answer_result(switchboard_uuid, call_id, token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def put_switchboard_queued_call_answer_result(self, switchboard_uuid, call_id, token=None):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'queued', call_id, 'answer')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def switchboard_hold_call(self, switchboard_uuid, call_id, token=VALID_TOKEN):
        response = self.put_switchboard_held_call_result(switchboard_uuid, call_id, token)
        assert_that(response.status_code, equal_to(204))

    def put_switchboard_held_call_result(self, switchboard_uuid, call_id, token=None):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'held', call_id)
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

    def switchboard_held_calls(self, switchboard_uuid, token=VALID_TOKEN):
        response = self.get_switchboard_held_calls_result(switchboard_uuid, token)

        assert_that(response.status_code, equal_to(200))
        return response.json()

    def get_switchboard_held_calls_result(self, switchboard_uuid, token=None):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'held')
        return requests.get(url, headers={'X-Auth-Token': token}, verify=False)

    def switchboard_answer_held_call(self, switchboard_uuid, call_id, token):
        response = self.put_switchboard_held_call_answer_result(switchboard_uuid, call_id, token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def put_switchboard_held_call_answer_result(self, switchboard_uuid, call_id, token=None):
        url = self.url('switchboards', switchboard_uuid, 'calls', 'held', call_id, 'answer')
        return requests.put(url, headers={'X-Auth-Token': token}, verify=False)

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


def new_call_id():
    return format(time.time(), '.2f')
