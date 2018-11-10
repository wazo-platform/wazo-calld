# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests
from requests.utils import quote


class Client(object):

    def __init__(self, host, port, prefix='/api', https=False):
        self.host = host
        self.port = port
        self._prefix = prefix
        self._https = https

    def url(self, *fragments):
        base = '{scheme}://{host}:{port}{prefix}'.format(
            scheme='https' if self._https else 'http',
            host=self.host,
            port=self.port,
            prefix=self._prefix,
        )
        if fragments:
            base = "{base}/{path}".format(base=base, path='/'.join(quote(fragment) for fragment in fragments))

        return base

    def get_user_history(self, user_jid, limit=None):
        endpoint = 'messages'
        url = self.url(endpoint, user_jid)
        params = {}
        if limit:
            params['limit'] = limit
        r = requests.get(url, params=params)
        if r.status_code != 200:
            r.raise_for_status()

        return r.json()

    def get_user_history_with_participant(self, user_jid, participant_jid, limit=None):
        endpoint = 'messages'
        url = self.url(endpoint, user_jid, participant_jid)
        params = {}
        if limit:
            params['limit'] = limit
        r = requests.get(url, params=params)

        if r.status_code != 200:
            r.raise_for_status()

        return r.json()

    def send_message(self, from_jid, to_jid, msg):
        endpoint = 'messages'
        url = self.url(endpoint)
        body = {'caller': from_jid,
                'to': to_jid,
                'body': self._escape_buggy_symbols(msg)}
        r = requests.post(url, json=body)

        if r.status_code != 204:
            r.raise_for_status()

    def _escape_buggy_symbols(self, msg):
        return msg.replace('&', '#26')
