# Copyright 2015-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


class QueuedCall:
    def __init__(self, id_):
        self.id = id_
        self.creation_time = None
        self.caller_id_name = ''
        self.caller_id_number = ''


class HeldCall:
    def __init__(self, id_):
        self.id = id_
        self.caller_id_name = ''
        self.caller_id_number = ''
