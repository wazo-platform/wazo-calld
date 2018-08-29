# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class _BaseEvent(object):

    required_acl = 'events.{}'

    def marshal(self):
        return self._body


class _BaseCallListEvent(_BaseEvent):

    def __init__(self, application_uuid, call):
        self.routing_key = self.routing_key.format(application_uuid)
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': str(application_uuid),
            'call': call,
        }


class CallEntered(_BaseCallListEvent):
    name = 'application_call_entered'
    routing_key = 'applications.{}.calls.created'
