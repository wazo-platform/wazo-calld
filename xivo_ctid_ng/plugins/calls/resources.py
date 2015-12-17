# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from flask import request

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.rest_api import AuthResource

from . import validator

logger = logging.getLogger(__name__)


class CallsResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('ctid-ng.calls.list')
    def get(self):
        application_filter = request.args.get('application')
        application_instance_filter = request.args.get('application_instance')

        calls = self.calls_service.list_calls(application_filter, application_instance_filter)

        return {
            'items': [call.to_dict() for call in calls],
        }, 200

    @required_acl('ctid-ng.calls.originate')
    def post(self):
        request_body = request.json

        validator.validate_originate_body(request_body)

        call_id = self.calls_service.originate(request_body)

        return {'call_id': call_id}, 201


class CallResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('ctid-ng.calls.get')
    def get(self, call_id):
        call = self.calls_service.get(call_id)

        return call.to_dict()

    @required_acl('ctid-ng.calls.hangup')
    def delete(self, call_id):
        self.calls_service.hangup(call_id)

        return None, 204


class ConnectCallToUserResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('ctid-ng.calls.connect_user')
    def put(self, call_id, user_id):
        new_call_id = self.calls_service.connect_user(call_id, user_id)
        new_call = self.calls_service.get(new_call_id)

        return new_call.to_dict()
