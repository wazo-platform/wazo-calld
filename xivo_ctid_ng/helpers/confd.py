# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from requests import HTTPError
from requests import RequestException

from xivo_ctid_ng.exceptions import XiVOConfdUnreachable

from .exceptions import InvalidUserUUID
from .exceptions import InvalidUserLine
from .exceptions import NoSuchUserVoicemail
from .exceptions import NoSuchVoicemail
from .exceptions import UserMissingMainLine


def not_found(error):
    return error.response is not None and error.response.status_code == 404


class User:

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

    def mobile_phone_number(self):
        try:
            return self._confd.users.get(self.uuid)['mobile_phone_number']
        except HTTPError as e:
            if not_found(e):
                raise InvalidUserUUID(self.uuid)
            raise
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)


class Line:

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
        # TODO PJSIP clean after migration
        protocol = line['protocol'].replace('sip', 'pjsip')
        return "{}/{}".format(protocol, line['name'])

    def interface_autoanswer(self):
        interface = self.interface()
        if interface.startswith('sccp/'):
            interface = '{}/autoanswer'.format(interface)
        return interface


class Conference:

    def __init__(self, tenant_uuid, conference_id, confd_client):
        self.tenant_uuid = tenant_uuid
        self.conference_id = conference_id
        self._confd = confd_client

    def exists(self):
        try:
            conferences = self._confd.conferences.list(tenant_uuid=self.tenant_uuid, recurse=True)['items']
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)
        return self.conference_id in (conference['id'] for conference in conferences)


def get_user_voicemail(user_uuid, confd_client):
    try:
        return confd_client.users.relations(user_uuid).get_voicemail()
    except HTTPError as e:
        if not_found(e):
            raise NoSuchUserVoicemail(user_uuid)
        raise
    except RequestException as e:
        raise XiVOConfdUnreachable(confd_client, e)


def get_voicemail(voicemail_id, confd_client):
    try:
        return confd_client.voicemails.get(voicemail_id)
    except HTTPError as e:
        if not_found(e):
            raise NoSuchVoicemail(voicemail_id)
        raise
    except RequestException as e:
        raise XiVOConfdUnreachable(confd_client, e)
