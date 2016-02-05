# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests

from hamcrest import assert_that, equal_to

from .constants import STASIS_APP_ARGS
from .constants import STASIS_APP_INSTANCE_NAME
from .constants import STASIS_APP_NAME


class StasisClient(object):

    def event_answer_connect(cls, from_, new_call_id):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "args": [
                STASIS_APP_INSTANCE_NAME,
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

    def event_stasis_start(self, channel_id, stasis_args=STASIS_APP_ARGS):
        url = 'http://localhost:5039/_send_ws_event'
        body = {
            "application": STASIS_APP_NAME,
            "args": stasis_args,
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

    def event_channel_destroyed(self, channel_id, creation_time=None, timestamp=None, connected_number=''):
        url = 'http://localhost:5039/_send_ws_event'
        creation_time = creation_time or "2016-02-04T15:10:21.225-0500"
        timestamp = timestamp or "2016-02-04T15:10:22.548-0500"
        body = {
            "application": STASIS_APP_NAME,
            "cause": 0,
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
