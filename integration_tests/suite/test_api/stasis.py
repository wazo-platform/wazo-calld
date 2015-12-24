# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests

from hamcrest import assert_that, equal_to

from .constants import STASIS_APP_NAME


class StasisClient(object):

    def event_answer_connect(cls, from_, new_call_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "args": [
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
                "name": "SIP/my-sip-00000020",
                "state": "Up"
            },
            "timestamp": "2015-12-16T15:14:04.269-0500",
            "type": "StasisStart"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    def event_hangup(cls, channel_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
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

    def event_new_channel(cls, channel_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "args": [],
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
                "id": channel_id,
                "language": "en_US",
                "name": "SIP/my-sip-00000020",
                "state": "Up"
            },
            "timestamp": "2015-12-16T15:14:04.269-0500",
            "type": "StasisStart"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))

    def event_channel_updated(cls, channel_id, state='Ring'):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
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
                "state": state
            },
            "timestamp": "2015-12-18T15:40:39.073-0500",
            "type": "ChannelStateChange"
        }

        response = requests.post(url, json=body)
        assert_that(response.status_code, equal_to(201))
