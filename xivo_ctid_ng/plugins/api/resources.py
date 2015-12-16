# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from flask import make_response
from flask.ext.restful import Resource
from pkg_resources import resource_string


class SwaggerResource(Resource):

    api_package = "xivo_ctid_ng.plugins.api"
    api_filename = "api.json"
    api_path = "/api/api.json"

    @classmethod
    def add_resource(cls, api):
        api.add_resource(cls, cls.api_path)

    def get(self):
        try:
            api_spec = resource_string(self.api_package, self.api_filename)
        except IOError:
            return {'error': "API spec does not exist"}, 404
        return make_response(api_spec, 200, {'Content-Type': 'application/json'})
