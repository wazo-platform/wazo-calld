# -*- coding: UTF-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json
import ssl
import socket

from websocket import create_connection
from .exceptions import XiVOWebsocketdError


class NotFoundException(Exception):
    pass


class WrongOPException(Exception):
    pass


class Client(object):

    _url_fmt = '{scheme}://{host}:{port}'

    def __init__(self, host, port, verify_certificate, wss=True, timeout=5, *args, **kwargs):
        self._host = host
        self._port = port
        self._wss = wss
        self._verify_certificate = verify_certificate
        self._timeout = timeout
        self._url = self._url_fmt.format(scheme='wss' if wss else 'ws', host=host, port=port)
        self._token_id = None

    def _presence(self, action):
        try:
            ws = create_connection(self._url,
                                   header=['X-Auth-Token: {}'.format(self._token_id)],
                                   timeout=self._timeout,
                                   sslopt=self._ssl_options())
        except socket.gaierror as e:
            raise XiVOWebsocketdError(self, e)
        except ssl.SSLError as e:
            raise XiVOWebsocketdError(self, e)
        except socket.WebSocketTimeOutException as e:
            raise XiVOWebsocketdError(self, e)

        try:
            result = json.loads(ws.recv())
            if result.get('op') != 'init' or result.get('code') != 0:
                raise WrongOPException(result)

            ws.send(json.dumps(action))
            result = json.loads(ws.recv())
        except ValueError:
            raise XiVOWebsocketdError(self, 'xivo-websocketd has closed session')
        except WrongOPException as e:
            raise XiVOWebsocketdError(self, 'xivo-websocketd does not initialize connection: "{}"'.format(e))
        finally:
            ws.close()

        if result.get('op') != action['op']:
            raise XiVOWebsocketdError(self, 'xivo-websocketd return: "{}"'.format(result))

        code = result.get('code')
        if code == 401:
            raise XiVOWebsocketdError(self, 'xivo-websocketd return unauthorized')
        elif code == 404:
            raise NotFoundException()
        elif code != 0:
            raise XiVOWebsocketdError(self, 'xivo-websocketd return NOK')

        return result

    def get_presence(self, user_uuid):
        action = {'op': 'get_presence', 'data': {'user_uuid': user_uuid}}
        result = self._presence(action)
        return result['msg']['presence']

    def set_presence(self, user_uuid, presence):
        action = {'op': 'presence', 'data': {'user_uuid': user_uuid, 'presence': presence}}
        self._presence(action)

    def _ssl_options(self):
        if self._verify_certificate is False:
            return {'cert_reqs': ssl.CERT_NONE}
        if self._verify_certificate is True:
            return {}
        if isinstance(self._verify_certificate, str):
            return {'cert_reqs': ssl.CERT_REQUIRED, 'ca_certs': self._verify_certificate}
        return {}

    def set_token(self, token):
        self._token_id = token
