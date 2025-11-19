# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from hamcrest import assert_that, has_entries, has_item
from wazo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.confd import MockVoicemail
from .helpers.constants import VALID_TENANT_MULTITENANT_1, XIVO_UUID
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy

NEW_MESSAGE_CONTENT = '''
;
; Message Information file
;
[message]
origmailbox=8000
context=default
macrocontext=
exten=voicemail
rdnis=8000
priority=7
callerchan=SIP/pph45z-00000005
callerid=\\\"Bob\\\" <1002>
origdate=Mon Aug 19 10:49:28 PM UTC 2024
origtime=1724107785
category=
msg_id=1724107785-00000002
flag=
duration=3
'''


class TestVoicemailBusConsume(IntegrationTest):
    asset = 'real_asterisk'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.confd.reset()

    def create_new_voicemail(self, number, context, content, message_name):
        base_path = '/var/spool/asterisk/voicemail'
        path = os.path.join(base_path, context, number, 'INBOX', message_name)
        self.docker_exec(['sh', '-c', f'echo "{content}" > {path}'], 'calld')

    def test_when_ami_message_waiting_then_bus_event(self):
        voicemail_id_1 = 111
        expected_message_id = '1724107785-00000002'
        tenant_voicemail = MockVoicemail(
            voicemail_id_1,
            '8000',
            'tenant-voicemail',
            'default',
            accesstype='global',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        self.confd.set_voicemails(tenant_voicemail)
        self.create_new_voicemail('8000', 'default', NEW_MESSAGE_CONTENT, 'msg0001.txt')

        events = self.bus.accumulator(
            headers={'name': 'global_voicemail_message_created'}
        )
        self.bus.send_message_waiting_event('8000', 'default')

        def assert_fn():
            assert_that(
                events.accumulate(),
                has_item(
                    has_entries(
                        name='global_voicemail_message_created',
                        origin_uuid=XIVO_UUID,
                        data=has_entries(
                            message_id=expected_message_id,
                            message=has_entries(
                                id=expected_message_id,
                                caller_id_name='Bob',
                                caller_id_num='1002',
                                voicemail=has_entries(
                                    id=voicemail_id_1,
                                    accesstype='global',
                                    name='tenant-voicemail',
                                ),
                            ),
                        ),
                    )
                ),
            )

        until.assert_(assert_fn, tries=5)
