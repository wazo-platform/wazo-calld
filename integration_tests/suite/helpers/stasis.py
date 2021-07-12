# Copyright 2015-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from hamcrest import assert_that, equal_to

from .constants import SOME_STASIS_APP


class StasisClient:

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        return 'http://{host}:{port}/{path}'.format(host=self._host,
                                                    port=self._port,
                                                    path='/'.join(parts))

    def event_answer_connect(self, from_, new_call_id, stasis_app, stasis_app_instance):
        url = self.url('_send_ws_event')
        body = {
            "application": stasis_app,
            "args": [
                stasis_app_instance,
                "dialed_from",
                from_
            ],
            "channel": {
                "accountcode": "",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-16T15:13:59.526-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "",
                    "priority": 1
                },
                "id": new_call_id,
                "language": "en_US",
                "name": "PJSIP/my-sip-00000020",
                "state": "Up"
            },
            "timestamp": "2015-12-16T15:14:04.269-0500",
            "type": "StasisStart"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    def event_hangup(self, channel_id):
        url = self.url('_send_ws_event')
        body = {
            "application": SOME_STASIS_APP,
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-18T15:40:32.439-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Ring"
            },
            "timestamp": "2015-12-18T15:40:39.073-0500",
            "type": "StasisEnd"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    def event_stasis_start(self, channel_id, stasis_app, stasis_app_instance, stasis_args=None):
        stasis_args = stasis_args or []
        url = self.url('_send_ws_event')
        body = {
            "application": stasis_app,
            "args": [stasis_app_instance] + stasis_args,
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2016-02-04T14:25:00.007-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Ring"
            },
            "timestamp": "2016-02-04T14:25:00.408-0500",
            "type": "StasisStart"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    def event_channel_destroyed(self, channel_id, stasis_app, line_id=None, cause=0, sip_call_id=None, creation_time=None, timestamp=None, connected_number=''):
        url = self.url('_send_ws_event')
        creation_time = creation_time or "2016-02-04T15:10:21.225-0500"
        timestamp = timestamp or "2016-02-04T15:10:22.548-0500"
        body = {
            "application": stasis_app,
            "cause": cause,
            "cause_txt": "Unknown",
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": connected_number
                },
                "channelvars": {
                    "WAZO_LINE_ID": line_id,
                    'WAZO_SIP_CALL_ID': sip_call_id,
                },
                "creationtime": creation_time,
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Down"
            },
            "timestamp": timestamp,
            "type": "ChannelDestroyed"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    def non_json_message(self):
        url = self.url('_send_ws_event')
        response = requests.post(url, data='')
        assert_that(response.status_code, equal_to(201))
