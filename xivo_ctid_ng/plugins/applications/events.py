# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class _BaseEvent(object):

    required_acl = 'events.{}'

    def marshal(self):
        return self._body


class _BaseCallItemEvent(_BaseEvent):

    def __init__(self, application_uuid, call):
        self.routing_key = self.routing_key.format(application_uuid, call['id'])
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': str(application_uuid),
            'call': call,
        }


class _BaseCallListEvent(_BaseEvent):

    def __init__(self, application_uuid, call):
        self.routing_key = self.routing_key.format(application_uuid)
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': str(application_uuid),
            'call': call,
        }


class _BaseNodeItemEvent(_BaseEvent):

    def __init__(self, application_uuid, node):
        self.routing_key = self.routing_key.format(application_uuid, node['uuid'])
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': str(application_uuid),
            'node': node
        }


class _BaseNodeListEvent(_BaseEvent):

    def __init__(self, application_uuid, node):
        self.routing_key = self.routing_key.format(application_uuid)
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': str(application_uuid),
            'node': node
        }


class _BaseSnoopItemEvent(_BaseEvent):

    def __init__(self, application_uuid, snoop):
        self.routing_key = self.routing_key.format(application_uuid, snoop['uuid'])
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': str(application_uuid),
            'snoop': snoop
        }


class DTMFReceived(_BaseEvent):

    name = 'application_call_dtmf_received'
    routing_key_tpl = 'applications.{}.calls.{}.dtmf.created'

    def __init__(self, application_uuid, call_id, dtmf):
        self.routing_key = self.routing_key_tpl.format(application_uuid, call_id)
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'application_uuid': application_uuid,
            'call_id': call_id,
            'dtmf': dtmf,
        }


class CallEntered(_BaseCallListEvent):
    name = 'application_call_entered'
    routing_key = 'applications.{}.calls.created'


class CallInitiated(_BaseCallListEvent):
    name = 'application_call_initiated'
    routing_key = 'applications.{}.calls.created'


class CallDeleted(_BaseCallItemEvent):
    name = 'application_call_deleted'
    routing_key = 'applications.{}.calls.{}.deleted'


class CallUpdated(_BaseCallItemEvent):
    name = 'application_call_updated'
    routing_key = 'applications.{}.calls.{}.updated'


class DestinationNodeCreated(_BaseNodeListEvent):
    name = 'application_destination_node_created'
    routing_key = 'applications.{}.nodes.created'


class NodeCreated(_BaseNodeListEvent):
    name = 'application_node_created'
    routing_key = 'applications.{}.nodes.created'


class NodeDeleted(_BaseNodeItemEvent):
    name = 'application_node_deleted'
    routing_key = 'applications.{}.nodes.{}.deleted'


class NodeUpdated(_BaseNodeItemEvent):
    name = 'application_node_updated'
    routing_key = 'applications.{}.nodes.{}.updated'


class SnoopCreated(_BaseSnoopItemEvent):
    name = 'application_snoop_created'
    routing_key = 'applications.{}.snoops.{}.created'


class SnoopDeleted(_BaseSnoopItemEvent):
    name = 'application_snoop_deleted'
    routing_key = 'applications.{}.snoops.{}.deleted'


class SnoopUpdated(_BaseSnoopItemEvent):
    name = 'application_snoop_updated'
    routing_key = 'applications.{}.snoops.{}.updated'
