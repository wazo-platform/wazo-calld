# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+


class Status(object):
    fail = 'fail'
    ok = 'ok'


class StatusService(object):
    def __init__(self, ari, bus_consumer):
        self._ari = ari
        self._bus_consumer = bus_consumer

    def ari_status(self):
        if self._ari.is_running():
            return Status.ok
        else:
            return Status.fail

    def bus_consumer_status(self):
        if self._bus_consumer.is_running():
            return Status.ok
        else:
            return Status.fail
