# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from requests import HTTPError
from requests import RequestException

from .exceptions import InvalidUserUUID
from .exceptions import UserHasNoLine
from .exceptions import XiVOConfdUnreachable


def not_found(error):
    return error.response is not None and error.response.status_code == 404


class User(object):

    def __init__(self, user_uuid, confd_client):
        self.uuid = user_uuid
        self._confd = confd_client

    def main_line(self):
        try:
            user_lines_of_user = self._confd.users.relations(self.uuid).list_lines()['items']
        except HTTPError as e:
            if not_found(e):
                raise InvalidUserUUID(self.uuid)
            raise
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)

        main_line_ids = [user_line['line_id'] for user_line in user_lines_of_user if user_line['main_line'] is True]
        if not main_line_ids:
            raise UserHasNoLine(self.uuid)
        return Line(main_line_ids[0], self._confd, )


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
            raise XiVOConfdUnreachable(self._confd_config, e)

    def context(self):
        line = self._get()
        return line['context']

    def interface(self):
        line = self._get()
        return "{}/{}".format(line['protocol'], line['name'])
