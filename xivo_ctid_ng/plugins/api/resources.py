# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import collections
import yaml
import logging

from flask import make_response
from flask.ext.restful import Resource
from pkg_resources import resource_string, iter_entry_points

logger = logging.getLogger(__name__)


class SwaggerResource(Resource):

    api_filename = "api.yml"

    def get(self):
        api_spec = {}
        for module in iter_entry_points(group='xivo_ctid_ng.plugins'):
            try:
                spec = yaml.load(resource_string(module.module_name, self.api_filename))
                api_spec = self.update(api_spec, spec)
            except IOError:
                logger.debug('API spec for module "%s" does not exist', module.module_name)

        if not api_spec.get('info'):
            return {'error': "API spec does not exist"}, 404

        return make_response(yaml.dump(api_spec), 200, {'Content-Type': 'application/x-yaml'})

    def update(self, a, b):
        for key, value in b.iteritems():
            if isinstance(value, collections.Mapping):
                result = self.update(a.get(key, {}), value)
                a[key] = result
            else:
                a[key] = b[key]
        return a
