# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+


class Transfer(object):

    def __init__(self, id_):
        self.id_ = id_
        self.transferred_call = None
        self.initiator_call = None
        self.recipient_call = None
        self.status = 'invalid'

    def to_dict(self):
        return {
            'id': self.id_,
            'transferred_call': self.transferred_call,
            'initiator_call': self.initiator_call,
            'recipient_call': self.recipient_call,
            'status': self.status,
        }
