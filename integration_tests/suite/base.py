# -*- coding: utf-8 -*-

# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import requests
import os
import logging

from hamcrest import assert_that, equal_to
from requests.packages import urllib3
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

logger = logging.getLogger(__name__)

urllib3.disable_warnings()

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', 'assets')
VALID_TOKEN = 'valid-token'


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'ctid-ng'

    @classmethod
    def get_calls_result(cls, token=None):
        url = u'https://localhost:9500/1.0/calls'
        result = requests.get(url,
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def list_calls(cls, token=VALID_TOKEN):
        response = cls.get_calls_result(token=token)
        assert_that(response.status_code, equal_to(200))
        return response.json()

    @classmethod
    def get_call_result(cls, call_id, token=None):
        url = u'https://localhost:9500/1.0/calls/{call_id}'
        result = requests.get(url.format(call_id=call_id),
                              headers={'X-Auth-Token': token},
                              verify=False)
        return result

    @classmethod
    def post_calls_result(cls, token=None):
        url = u'https://localhost:9500/1.0/calls'
        result = requests.post(url,
                               headers={'X-Auth-Token': token},
                               verify=False)
        return result

    @classmethod
    def delete_call_result(cls, call_id, token=None):
        url = u'https://localhost:9500/1.0/calls/{call_id}'
        result = requests.delete(url.format(call_id=call_id),
                                 headers={'X-Auth-Token': token},
                                 verify=False)
        return result

    @classmethod
    def set_ari_channels(cls, channels):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'channels',
                'content': channels}
        requests.post(url, json=body)

    @classmethod
    def set_ari_channel_variable(cls, variables):
        url = 'http://localhost:5039/_set_response'
        body = {'response': 'channel_variable',
                'content': variables}
        requests.post(url, json=body)

    @classmethod
    def set_confd_users(cls, users):
        url = 'https://localhost:9486/_set_response'
        body = {'response': 'users',
                'content': users}
        requests.post(url,
                      json=body,
                      verify=False)
