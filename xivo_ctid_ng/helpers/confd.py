# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from requests import HTTPError
from requests import RequestException

from xivo_ctid_ng.core.exceptions import XiVOConfdUnreachable

from .exceptions import InvalidUserUUID
from .exceptions import InvalidUserLine
from .exceptions import UserMissingMainLine


def not_found(error):
    return error.response is not None and error.response.status_code == 404


class User(object):

    def __init__(self, user_uuid, confd_client):
        self.uuid = user_uuid
        self._confd = confd_client

    def main_line(self):
        try:
            lines = self._confd.users.get(self.uuid)['lines']
        except HTTPError as e:
            if not_found(e):
                raise InvalidUserUUID(self.uuid)
            raise
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)

        try:
            main_line_id = lines[0]['id']
        except IndexError:
            raise UserMissingMainLine(self.uuid)
        return Line(main_line_id, self._confd)

    def line(self, line_id):
        try:
            lines = self._confd.users.get(self.uuid)['lines']
        except HTTPError as e:
            if not_found(e):
                raise InvalidUserUUID(self.uuid)
            raise
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)

        valid_line_ids = [line['id'] for line in lines]
        if line_id not in valid_line_ids:
            raise InvalidUserLine(self.uuid, line_id)

        return Line(line_id, self._confd)


class Line(object):

    def __init__(self, line_id, confd_client):
        self.id = line_id
        self._confd = confd_client

    def _get(self):
        try:
            return self._confd.lines.get(self.id)
        except HTTPError as e:
            raise
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)

    def context(self):
        line = self._get()
        return line['context']

    def interface(self):
        line = self._get()
        return "{}/{}".format(line['protocol'], line['name'])
