# -*- coding: utf-8 -*-
# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from collections import defaultdict


class Status(object):
    fail = 'fail'
    ok = 'ok'


class StatusAggregator(object):

    def __init__(self):
        self._providers = []

    def add_provider(self, status_provider):
        self._providers.append(status_provider)

    def status(self):
        status = _default_dict()
        for provider in self._providers:
            provider(status)
        return status


def _default_dict():
    return defaultdict(_default_dict)


class TokenStatus(object):

    def __init__(self):
        self.has_token = False

    def token_change_callback(self, token):
        self.has_token = True

    def provide_status(self, status):
        status['service_token'] = Status.ok if self.has_token else Status.fail
