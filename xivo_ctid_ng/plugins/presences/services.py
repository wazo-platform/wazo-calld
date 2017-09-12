# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

import logging
from datetime import datetime, timedelta

import requests
from xivo.consul_helpers import ServiceFinder
from xivo_auth_client import Client as AuthClient
from xivo_ctid_ng_client import Client as CtidNgClient
from xivo_bus.resources.cti.event import UserStatusUpdateEvent

from .exceptions import (InvalidCredentials,
                         MissingCredentials,
                         NoSuchUser,
                         NoSuchLine,
                         XiVOAuthUnreachable,
                         XiVOCtidUnreachable,
                         XiVOCtidNgUnreachable)

logger = logging.getLogger(__name__)


def _extract_status_code(exception):
    response = getattr(exception, 'response', None)
    return getattr(response, 'status_code', None)


class UserPresencesService(object):

    def __init__(self, bus_publisher, ctid_client, ctid_config, local_xivo_uuid, ctid_ng_client_factory):
        self._bus_publisher = bus_publisher
        self._ctid_client = ctid_client
        self._ctid_config = ctid_config
        self._xivo_uuid = local_xivo_uuid
        self._ctid_ng_client_factory = ctid_ng_client_factory

    def get_local_presence(self, user_uuid):
        logger.debug('looking for local user presence: %s', user_uuid)
        try:
            response = self._ctid_client.users.get(user_uuid)
            return response['origin_uuid'], response['presence']
        except requests.RequestException as e:
            status_code = _extract_status_code(e)
            if status_code == 404:
                raise NoSuchUser(self._xivo_uuid, user_uuid)
            else:
                raise XiVOCtidUnreachable(self._ctid_config, e)

    def get_remote_presence(self, xivo_uuid, user_uuid):
        logger.debug('looking for remote user presence: %s@%s', user_uuid, xivo_uuid)
        c = self._ctid_ng_client_factory.new_ctid_ng_client(xivo_uuid)
        try:
            response = c.user_presences.get_presence(user_uuid, xivo_uuid=xivo_uuid)
            return response['xivo_uuid'], response['presence']
        except requests.RequestException as e:
            status_code = _extract_status_code(e)
            if status_code == 401:
                raise InvalidCredentials(xivo_uuid)
            elif status_code == 404:
                raise NoSuchUser(xivo_uuid, user_uuid)
            else:
                raise XiVOCtidNgUnreachable(xivo_uuid, e)

    def get_presence(self, xivo_uuid, user_uuid):
        if xivo_uuid in [None, self._xivo_uuid]:
            return self.get_local_presence(user_uuid)
        else:
            return self.get_remote_presence(xivo_uuid, user_uuid)

    def update_presence(self, user_uuid, status):
        bus_event = UserStatusUpdateEvent(user_uuid, status)
        self._bus_publisher.publish(bus_event, headers={'user_uuid': user_uuid})


class LinePresencesService(object):

    def __init__(self, ctid_client, ctid_config, local_xivo_uuid, ctid_ng_client_factory):
        self._ctid_client = ctid_client
        self._ctid_config = ctid_config
        self._xivo_uuid = local_xivo_uuid
        self._ctid_ng_client_factory = ctid_ng_client_factory

    def get_presence(self, xivo_uuid, line_id):
        if xivo_uuid in [None, self._xivo_uuid]:
            return self.get_local_presence(line_id)
        else:
            return self.get_remote_presence(xivo_uuid, line_id)

    def get_local_presence(self, line_id):
        try:
            response = self._ctid_client.endpoints.get(line_id)
            return response['id'], response['origin_uuid'], response['status']
        except requests.RequestException as e:
            status_code = _extract_status_code(e)
            if status_code == 404:
                raise NoSuchLine(self._xivo_uuid, line_id)
            else:
                raise XiVOCtidUnreachable(self._ctid_config, e)

    def get_remote_presence(self, xivo_uuid, line_id):
        logger.debug('looking for remote line presence: %s@%s', line_id, xivo_uuid)
        c = self._ctid_ng_client_factory.new_ctid_ng_client(xivo_uuid)
        try:
            response = c.line_presences.get_presence(line_id, xivo_uuid=xivo_uuid)
            return response['line_id'], response['xivo_uuid'], response['presence']
        except requests.RequestException as e:
            status_code = _extract_status_code(e)
            if status_code == 401:
                raise InvalidCredentials(xivo_uuid)
            elif status_code == 404:
                raise NoSuchLine(xivo_uuid, line_id)
            else:
                raise XiVOCtidNgUnreachable(xivo_uuid, e)


class CtidNgClientFactory(object):

    def __init__(self, consul_config, remote_credentials):
        self.finder = ServiceFinder(consul_config)
        self._auth_tokens = {}
        self._credentials = {}
        for remote in remote_credentials.itervalues():
            uuid = remote.get('xivo_uuid')
            id_ = remote.get('service_id')
            key = remote.get('service_key')
            if not uuid or not id_ or not key:
                continue
            self._credentials[uuid] = {'service_id': id_, 'service_key': key}

    def get_token(self, xivo_uuid):
        token = self._auth_tokens.get(xivo_uuid)
        if not self._is_valid(token):
            credentials = self._credentials.get(xivo_uuid)
            if not credentials:
                raise MissingCredentials(xivo_uuid)

            auth_config = self.find_service_config('xivo-auth', xivo_uuid)
            if not auth_config:
                raise XiVOAuthUnreachable(xivo_uuid, 'no running service found')

            client = AuthClient(username=credentials['service_id'],
                                password=credentials['service_key'],
                                host=auth_config['Address'],
                                port=auth_config['Port'],
                                verify_certificate=False)
            try:
                self._auth_tokens[xivo_uuid] = token = client.token.new('xivo_service')
            except requests.RequestException:
                raise InvalidCredentials(xivo_uuid)
        return token['token']

    def new_ctid_ng_client(self, xivo_uuid):
        remote_token = self.get_token(xivo_uuid)
        if not remote_token:
            raise XiVOCtidNgUnreachable(xivo_uuid, 'failed to retrieve a token')

        ctid_ng_config = self.find_service_config('xivo-ctid-ng', xivo_uuid)
        if not ctid_ng_config:
            raise XiVOCtidNgUnreachable(xivo_uuid, 'no running service found')

        return CtidNgClient(host=ctid_ng_config['Address'],
                            port=ctid_ng_config['Port'],
                            verify_certificate=False,
                            token=remote_token)

    def find_service_config(self, service_name, service_uuid):
        for service in self.finder.list_healthy_services(service_name, service_uuid):
            return service

    def _is_valid(self, token):
        very_soon = (datetime.utcnow() + timedelta(seconds=5.0)).isoformat()
        return token and token.get('utc_expires_at') > very_soon
