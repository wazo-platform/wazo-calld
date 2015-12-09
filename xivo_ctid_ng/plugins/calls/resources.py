# -*- coding: utf-8 -*-
# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import logging

from flask import request

from xivo_ctid_ng.core.rest_api import AuthResource

from . import validator

logger = logging.getLogger(__name__)


class CallsResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    def get(self):
        token = request.headers['X-Auth-Token']
        self.calls_service.set_confd_token(token)
        application_filter = request.args.get('application')

        calls = self.calls_service.list_calls(application_filter)

        return {
            'items': [call.to_dict() for call in calls],
        }, 200

    def post(self):
        token = request.headers['X-Auth-Token']
        self.calls_service.set_confd_token(token)
        request_body = request.json

        validator.validate_originate_body(request_body)

        call_id = self.calls_service.originate(request_body)

        return {'call_id': call_id}, 201


class CallResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    def get(self, call_id):
        token = request.headers['X-Auth-Token']
        self.calls_service.set_confd_token(token)

        call = self.calls_service.get(call_id)

        return call.to_dict()

    def delete(self, call_id):
        self.calls_service.hangup(call_id)

        return None, 204
