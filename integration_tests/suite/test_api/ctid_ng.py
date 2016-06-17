# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import requests
import time

from contextlib import contextmanager
from hamcrest import assert_that, equal_to

from .constants import VALID_TOKEN


class CtidNgClient(object):

    def is_up(self):
        url = u'https://localhost:9500/'
        try:
            response = requests.get(url, verify=False)
            return response.status_code == 404
        except requests.RequestException:
            return False

    def get_calls_result(self, application=None, application_instance=None, token=None):
        url = u'https://localhost:9500/1.0/calls'
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

    def get_call_result(self, call_id, token=None):
        url = u'https://localhost:9500/1.0/calls/{call_id}'
        result = requests.get(url.format(call_id=call_id),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_call(self, call_id, token=VALID_TOKEN):
        response = self.get_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def post_call_result(self, source, priority, extension, context, variables=None, token=None):
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
            body.update({'variables': variables})

        return self.post_call_raw(body, token)

    def post_call_raw(self, body, token=None):
        url = u'https://localhost:9500/1.0/calls'
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def originate(self, source, priority, extension, context, variables=None, token=VALID_TOKEN):
        response = self.post_call_result(source, priority, extension, context, variables, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def post_user_me_call_result(self, body, token=None):
        url = u'https://localhost:9500/1.0/users/me/calls'
        result = requests.post(url,
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def originate_me(self, extension, variables=None, token=VALID_TOKEN):
        body = {
            'extension': extension
        }
        if variables:
            body['variables'] = variables
        response = self.post_user_me_call_result(body, token=token)
        assert_that(response.status_code, equal_to(201))
        return response.json()

    def delete_call_result(self, call_id, token=None):
        url = u'https://localhost:9500/1.0/calls/{call_id}'
        result = requests.delete(url.format(call_id=call_id),
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def hangup_call(self, call_id, token=VALID_TOKEN):
        response = self.delete_call_result(call_id, token=token)
        assert_that(response.status_code, equal_to(204))

    def get_plugins_result(self, token=None):
        url = u'https://localhost:9500/1.0/plugins'
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def put_call_user_result(self, call_id, user_uuid, token):
        url = u'https://localhost:9500/1.0/calls/{call_id}/user/{user_uuid}'
        result = requests.put(url.format(call_id=call_id, user_uuid=user_uuid),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def connect_user(self, call_id, user_uuid):
        response = self.put_call_user_result(call_id, user_uuid, token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def post_transfer_result(self, body, token=None):
        result = requests.post('https://localhost:9500/1.0/transfers',
                               json=body,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def create_transfer(self, transferred_call, initiator_call, context, exten):
        body = {
            'transferred_call': transferred_call,
            'initiator_call': initiator_call,
            'context': context,
            'exten': exten,
            'flow': 'attended',
        }
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

    def put_complete_transfer_result(self, transfer_id, token=None):
        url = u'https://localhost:9500/1.0/transfers/{transfer_id}/complete'
        result = requests.put(url.format(transfer_id=transfer_id),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def complete_transfer(self, transfer_id):
        response = self.put_complete_transfer_result(transfer_id,
                                                     token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(204))

    def delete_transfer_result(self, transfer_id, token=None):
        url = u'https://localhost:9500/1.0/transfers/{transfer_id}'
        result = requests.delete(url.format(transfer_id=transfer_id),
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    def cancel_transfer(self, transfer_id):
        response = self.delete_transfer_result(transfer_id,
                                               token=VALID_TOKEN)
        assert_that(response.status_code, equal_to(204))

    def get_transfer_result(self, transfer_id, token=None):
        url = u'https://localhost:9500/1.0/transfers/{transfer_id}'
        result = requests.get(url.format(transfer_id=transfer_id),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    def get_transfer(self, transfer_id, token=VALID_TOKEN):
        response = self.get_transfer_result(transfer_id, token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    def post_chat_result(self, chat_msg, token=None):
        result = requests.post('https://localhost:9500/1.0/chats',
                               json=chat_msg.as_chat_body(),
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    def post_user_chat_result(self, chat_msg, token=None):
        result = requests.post('https://localhost:9500/1.0/users/me/chats',
                               json=chat_msg.as_user_chat_body(),
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

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
