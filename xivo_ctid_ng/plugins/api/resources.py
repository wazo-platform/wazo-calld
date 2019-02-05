# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import yaml

from flask import make_response
from flask_restful import Resource
from xivo.chain_map import ChainMap
from xivo.rest_api_helpers import load_all_api_specs

logger = logging.getLogger(__name__)


class SwaggerResource(Resource):

    api_filename = "api.yml"

    def get(self):
        api_spec = ChainMap(*load_all_api_specs('xivo_ctid_ng.plugins', self.api_filename))

        if not api_spec.get('info'):
            return {'error': "API spec does not exist"}, 404

        return make_response(yaml.dump(dict(api_spec)), 200, {'Content-Type': 'application/x-yaml'})
