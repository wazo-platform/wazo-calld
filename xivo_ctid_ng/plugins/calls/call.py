# -*- coding: utf-8 -*-
# Copyright 2015-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class Call(object):

    def __init__(self, id_):
        self.id_ = id_
        self.creation_time = None
        self.bridges = []
        self.status = 'Down'
        self.talking_to = []
        self.user_uuid = None
        self.caller_id_name = ''
        self.caller_id_number = ''
        self.peer_caller_id_name = ''
        self.peer_caller_id_number = ''
        self.on_hold = False
        self.is_caller = False

    def to_dict(self):
        return {
            'bridges': self.bridges,
            'call_id': self.id_,
            'caller_id_name': self.caller_id_name,
            'caller_id_number': self.caller_id_number,
            'peer_caller_id_name': self.peer_caller_id_name,
            'peer_caller_id_number': self.peer_caller_id_number,
            'creation_time': self.creation_time,
            'status': self.status,
            'on_hold': self.on_hold,
            'talking_to': self.talking_to,
            'user_uuid': self.user_uuid,
            'is_caller': self.is_caller,
        }
