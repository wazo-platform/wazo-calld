# -*- coding: UTF-8 -*-

# Copyright (C) 2015 Avencall
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from .resources import CallResource, CallsResource
from .services import CallsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']

        calls_service = CallsService(ari_config=config['ari']['connection'], confd_config=config['confd'])
        token_changed_subscribe(calls_service.set_confd_token)

        api.add_resource(CallsResource, '/calls', resource_class_args=[calls_service])
        api.add_resource(CallResource, '/calls/<call_id>', resource_class_args=[calls_service])
