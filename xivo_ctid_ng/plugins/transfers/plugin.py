# -*- coding: UTF-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from .services import TransfersService
from .stasis import TransfersStasis
from .resources import TransfersResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']

        transfers_service = TransfersService(ari.client)
        transfers_stasis = TransfersStasis(ari.client, transfers_service, config['uuid'])
        transfers_stasis.subscribe()

        api.add_resource(TransfersResource, '/transfers', resource_class_args=[transfers_service])
