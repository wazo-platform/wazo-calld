# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


class Call(object):

    def __init__(self, id_, creation_time):
        self.id_ = id_
        self.creation_time = creation_time
        self.bridges = []
        self.status = 'Down'
        self.talking_to = []
        self.user_uuid = None

    def to_dict(self):
        return {
            'bridges': self.bridges,
            'call_id': self.id_,
            'creation_time': self.creation_time,
            'status': self.status,
            'talking_to': self.talking_to,
            'user_uuid': self.user_uuid,
        }
