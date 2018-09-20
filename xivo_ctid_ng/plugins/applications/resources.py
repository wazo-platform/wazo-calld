# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource

from .schema import (
    application_call_request_schema,
    application_call_schema,
    application_node_schema,
    application_playback_schema,
    application_schema,
)


class ApplicationItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.read')
    def get(self, application_uuid):
        application = self._service.get_application(application_uuid)
        return application_schema.dump(application).data


class ApplicationCallItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.calls.{call_id}.delete')
    def delete(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.delete_call(application_uuid, call_id)
        return '', 204


class ApplicationCallList(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.calls.create')
    def post(self, application_uuid):
        request_body = application_call_request_schema.load(request.get_json()).data
        self._service.get_application(application_uuid)
        call = self._service.originate(application_uuid, None, **request_body)
        return application_call_schema.dump(call).data, 201

    @required_acl('ctid-ng.applications.{application_uuid}.calls.read')
    def get(self, application_uuid):
        calls = self._service.list_calls(application_uuid)
        return {'items': application_call_schema.dump(calls, many=True).data}


class ApplicationCallMohStartList(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.calls.{call_id}.moh.{moh_uuid}.start.update')
    def put(self, application_uuid, call_id, moh_uuid):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.start_call_moh(call_id, moh_uuid)
        return '', 204


class ApplicationCallMohStopList(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.calls.{call_id}.moh.stop.update')
    def put(self, application_uuid, call_id):
        return '', 204


class ApplicationCallPlaybackList(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.calls.{call_id}.playbacks.create')
    def post(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        form = application_playback_schema.load(request.get_json()).data
        playback = self._service.create_playback(application_uuid, call_id, **form)
        return application_playback_schema.dump(playback).data


class ApplicationPlaybackItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.playbacks.{playback_uuid}.delete')
    def delete(self, application_uuid, playback_uuid):
        self._service.get_application(application_uuid)
        # TODO: verify that playback_uuid is in the application
        self._service.delete_playback(application_uuid, playback_uuid)
        return '', 204


class ApplicationNodeCallItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.{node_uuid}.calls.{call_id}.delete')
    def delete(self, application_uuid, node_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_node_uuid(application, node_uuid)
        self._service.leave_node(application_uuid, node_uuid, [call_id])
        return '', 204

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.{node_uuid}.calls.{call_id}.update')
    def put(self, application_uuid, node_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_node_uuid(application, node_uuid)
        self._service.join_node(application_uuid, node_uuid, [call_id], no_call_status_code=404)
        return '', 204


class ApplicationNodeCallList(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.{node_uuid}.calls.create')
    def post(self, application_uuid, node_uuid):
        application = self._service.get_application(application_uuid)
        # TODO: Check if node is in application
        #       But Asterisk doesn't allow to create empty node in an application ...
        self._service.get_node(application, node_uuid, verify_application=False)
        request_body = application_call_request_schema.load(request.get_json()).data
        call = self._service.originate(application_uuid, node_uuid, **request_body)
        return application_call_schema.dump(call).data, 201


class ApplicationNodeItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.{node_uuid}.read')
    def get(self, application_uuid, node_uuid):
        application = self._service.get_application(application_uuid)
        node = self._service.get_node(application, node_uuid)
        return application_node_schema.dump(node).data

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.{node_uuid}.delete')
    def delete(self, application_uuid, node_uuid):
        application = self._service.get_application(application_uuid)
        node = self._service.get_node(application, node_uuid)
        self._service.delete_node(application_uuid, node)
        return '', 204


class ApplicationNodeList(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.read')
    def get(self, application_uuid):
        self._service.get_application(application_uuid)
        nodes = self._service.list_nodes(application_uuid)
        return {'items': application_node_schema.dump(nodes, many=True).data}

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.create')
    def post(self, application_uuid):
        self._service.get_application(application_uuid)
        form = application_node_schema.load(request.get_json()).data
        call_ids = [call['id_'] for call in form.get('calls', [])]
        node = self._service.create_node_with_calls(application_uuid, call_ids)
        return application_node_schema.dump(node).data, 201
