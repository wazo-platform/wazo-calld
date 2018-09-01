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
    application_schema,
)


class ApplicationItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.read')
    def get(self, application_uuid):
        application = self._service.get_application(application_uuid)
        return application_schema.dump(application).data


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
        self._service.get_application(application_uuid)
        calls = self._service.list_calls(application_uuid)
        return {'items': application_call_schema.dump(calls, many=True).data}


class ApplicationNodeItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.nodes.{node_uuid}.read')
    def get(self, application_uuid, node_uuid):
        self._service.get_application(application_uuid)
        node = self._service.get_node(node_uuid)
        return application_node_schema.dump(node).data
