# -*- coding: utf-8 -*-
# Copyright 2015-2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class QueuedCall(object):

    def __init__(self, id_):
        self.id = id_
        self.creation_time = None
        self.caller_id_name = ''
        self.caller_id_number = ''
