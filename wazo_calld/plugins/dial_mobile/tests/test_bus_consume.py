# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock

from ..bus_consume import EventHandler
from ..services import DialMobileService


class TestEventHandler(TestCase):

    def setUp(self):
        self.service = Mock(DialMobileService)
        self.event_handler = EventHandler(self.service)

    def test_push_mobile_user_event(self):
        event = {
            'Event': 'UserEvent',
            'Privilege': 'user,all',
            'Channel': 'PJSIP/zcua59c9-00000015',
            'ChannelState': '4',
            'ChannelStateDesc': 'Ring',
            'CallerIDNum': '1005',
            'CallerIDName': 'Anastasia Romanov',
            'ConnectedLineNum': '1101',
            'ConnectedLineName': 'Alice WebRTC',
            'Language': 'fr_FR',
            'AccountCode': '',
            'Context': 'user',
            'Exten': 's',
            'Priority': '42',
            'Uniqueid': '1647612626.39',
            'Linkedid': '1647612626.39',
            'UserEvent': 'Pushmobile',
            'WAZO_DST_UUID': '89554a93-3761-43d2-9b14-a9b094bcbf1d',
            'WAZO_VIDEO_ENABLED': '0',
            'ChanVariable': {
                'CHANNEL(linkedid)': '1647612626.39',
                'CHANNEL(videonativeformat)': '(nothing)',
                'WAZO_ANSWER_TIME': '',
                'WAZO_CALL_RECORD_ACTIVE': '',
                'WAZO_CALL_RECORD_SIDE': 'caller',
                'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_ENTRY_CONTEXT': 'inside',
                'WAZO_ENTRY_EXTEN': '1101',
                'WAZO_LINE_ID': '83',
                'WAZO_LOCAL_CHAN_MATCH_UUID': '',
                'WAZO_SIP_CALL_ID': 'de9eb39fb7585796',
                'WAZO_SWITCHBOARD_QUEUE': '',
                'WAZO_SWITCHBOARD_HOLD': '',
                'WAZO_TENANT_UUID': '2c34c282-433e-4bb8-8d56-fec14ff7e1e9',
                'XIVO_BASE_EXTEN': '1101',
                'XIVO_ON_HOLD': '',
                'XIVO_USERUUID': 'def42192-837a-41e0-aa4e-86390e46eb17'
            }
        }

        self.event_handler._on_user_event(event)

        self.service.send_push_notification(
            '2c34c282-433e-4bb8-8d56-fec14ff7e1e9',
            '89554a93-3761-43d2-9b14-a9b094bcbf1d',
            '1647612626.39',
            'de9eb39fb7585796',
            'Anastasia Romanov',
            '1005',
            False,
        )

    def test_cancel_push_on_dial_end(self):
        event = {
            'CallerIDName': 'Anastasia Romanov',
            'CallerIDNum': '1005',
            'ChanVariable': {
                'CHANNEL(linkedid)': '1647871892.53',
                'CHANNEL(videonativeformat)': '(nothing)',
                'WAZO_ANSWER_TIME': '',
                'WAZO_CALL_RECORD_ACTIVE': '',
                'WAZO_CALL_RECORD_SIDE': 'caller',
                'WAZO_CHANNEL_DIRECTION': 'to-wazo',
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_ENTRY_CONTEXT': 'inside',
                'WAZO_ENTRY_EXTEN': '1101',
                'WAZO_LINE_ID': '83',
                'WAZO_LOCAL_CHAN_MATCH_UUID': '',
                'WAZO_SIP_CALL_ID': 'cf31ee68cec261d9',
                'WAZO_SWITCHBOARD_HOLD': '',
                'WAZO_SWITCHBOARD_QUEUE': '',
                'WAZO_TENANT_UUID': '2c34c282-433e-4bb8-8d56-fec14ff7e1e9',
                'XIVO_BASE_EXTEN': '1101',
                'XIVO_ON_HOLD': '',
                'XIVO_USERUUID': 'def42192-837a-41e0-aa4e-86390e46eb17'
            },
            'Channel': 'PJSIP/zcua59c9-0000001b',
            'ChannelState': '4',
            'ChannelStateDesc': 'Ring',
            'ConnectedLineName': 'Alice WebRTC',
            'ConnectedLineNum': '1101',
            'Context': 'user',
            'DestAccountCode': '',
            'DestCallerIDName': 'Alice WebRTC',
            'DestCallerIDNum': 's',
            'DestChanVariable': 'XIVO_USERUUID=',
            'DestChannel': 'Local/ycetqvtr@wazo_wait_for_registration-0000000d;1',
            'DestChannelState': '5',
            'DestChannelStateDesc': 'Ringing',
            'DestConnectedLineName': 'Anastasia Romanov',
            'DestConnectedLineNum': '1005',
            'DestContext': 'wazo_wait_for_registration',
            'DestExten': 's',
            'DestLanguage': 'en',
            'DestLinkedid': '1647871892.53',
            'DestPriority': '1',
            'DestUniqueid': '1647871892.54',
            'DialStatus': 'NOANSWER',
            'Event': 'DialEnd',
            'Exten': 's',
            'Language': 'fr_FR',
            'Linkedid': '1647871892.53',
            'Priority': '44',
            'Privilege': 'call,all',
            'Uniqueid': '1647871892.53',
        }

        self.event_handler._on_dial_end(event)

        self.service.cancel_push_mobile('1647871892.53')
