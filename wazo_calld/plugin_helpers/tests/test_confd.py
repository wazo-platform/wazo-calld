# Copyright 2016-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock

import requests
from hamcrest import assert_that, calling, equal_to, raises

from ..confd import Line, get_all_voicemails, get_voicemail
from ..exceptions import NoSuchVoicemail, WazoConfdUnreachable


class TestLine(TestCase):
    def setUp(self):
        self.confd_client = Mock()
        self.line = Line(42, self.confd_client)

    def test_request_exception_is_transformed_in_confd_exception(self):
        self.confd_client.lines.get.side_effect = requests.RequestException

        assert_that(calling(self.line._get).with_args(), raises(WazoConfdUnreachable))

    def test_line_interface_autoanswer_sip(self):
        self.confd_client.lines.get.return_value = {
            'protocol': 'sip',
            'name': 'abcdef',
        }
        assert_that(self.line.interface_autoanswer(), equal_to('pjsip/abcdef'))

    def test_line_interface_autoanswer_sccp(self):
        self.confd_client.lines.get.return_value = {
            'protocol': 'sccp',
            'name': 'abcdef',
        }
        assert_that(
            self.line.interface_autoanswer(), equal_to('sccp/abcdef/autoanswer')
        )


class TestGetVoicemail(TestCase):
    def setUp(self):
        self.confd_client = Mock()

    def test_returns_voicemail(self):
        vm = {'id': 1, 'name': 'vm', 'number': '100', 'context': 'default'}
        self.confd_client.voicemails.get.return_value = vm

        result = get_voicemail('tenant-1', 1, self.confd_client)

        assert_that(result, equal_to(vm))
        self.confd_client.voicemails.get.assert_called_once_with(
            1, tenant_uuid='tenant-1'
        )

    def test_not_found_raises_no_such_voicemail(self):
        response = Mock(status_code=404)
        self.confd_client.voicemails.get.side_effect = requests.HTTPError(
            response=response
        )

        assert_that(
            calling(get_voicemail).with_args('tenant-1', 999, self.confd_client),
            raises(NoSuchVoicemail),
        )

    def test_request_exception_raises_confd_unreachable(self):
        self.confd_client.voicemails.get.side_effect = requests.RequestException

        assert_that(
            calling(get_voicemail).with_args('tenant-1', 1, self.confd_client),
            raises(WazoConfdUnreachable),
        )


class TestGetAllVoicemails(TestCase):
    def setUp(self):
        self.confd_client = Mock()

    def test_returns_items(self):
        vms = [{'id': 1}, {'id': 2}]
        self.confd_client.voicemails.list.return_value = {'items': vms, 'total': 2}

        result = get_all_voicemails(
            self.confd_client, tenant_uuid='tenant-1', recurse=False
        )

        assert_that(result, equal_to(vms))
        self.confd_client.voicemails.list.assert_called_once_with(
            tenant_uuid='tenant-1', recurse=False
        )

    def test_passes_accesstype_filter(self):
        self.confd_client.voicemails.list.return_value = {'items': [], 'total': 0}

        get_all_voicemails(self.confd_client, tenant_uuid='t', accesstype='global')

        self.confd_client.voicemails.list.assert_called_once_with(
            tenant_uuid='t', accesstype='global'
        )

    def test_not_found_returns_empty(self):
        response = Mock(status_code=404)
        self.confd_client.voicemails.list.side_effect = requests.HTTPError(
            response=response
        )

        result = get_all_voicemails(self.confd_client, tenant_uuid='t')

        assert_that(result, equal_to([]))

    def test_request_exception_raises_confd_unreachable(self):
        self.confd_client.voicemails.list.side_effect = requests.RequestException

        assert_that(
            calling(get_all_voicemails).with_args(self.confd_client, tenant_uuid='t'),
            raises(WazoConfdUnreachable),
        )
