# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class ApplicationNotifier(object):

    def __init__(self, bus):
        self._bus = bus
