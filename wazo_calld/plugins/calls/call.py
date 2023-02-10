# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


class Call:
    def __init__(self, id_):
        self.id_ = id_
        self.conversation_id = None
        self.creation_time = None
        self.bridges = []
        self.status = 'Down'
        self.talking_to = {}
        self.user_uuid = None
        self.tenant_uuid = None
        self.caller_id_name = ''
        self.caller_id_number = ''
        self.peer_caller_id_name = ''
        self.peer_caller_id_number = ''
        self.on_hold = False
        self.muted = False
        self.record_state = 'inactive'
        self.is_caller = False
        self.dialed_extension = None
        self.sip_call_id = None
        self.line_id = None
        self.is_video = False
        self.answer_time = None
        self.hangup_time = None
        self.direction = 'unknown'
