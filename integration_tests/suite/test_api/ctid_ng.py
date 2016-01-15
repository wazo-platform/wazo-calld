# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests
import time

from hamcrest import assert_that, equal_to

from .constants import VALID_TOKEN


class CtidNgClient(object):

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


def new_call_id():
    return format(time.time(), '.2f')
