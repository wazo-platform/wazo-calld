# -*- coding: UTF-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_amid_client import Client as AmidClient

from .resources import TransferResource
from .resources import TransferCompleteResource
from .resources import TransfersResource
from .services import TransfersService
from .stasis import TransfersStasis
from .state import state_factory
from .state_persistor import StatePersistor


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        state_persistor = StatePersistor(ari.client)

        transfers_service = TransfersService(ari.client, amid_client, state_factory, state_persistor)

        transfers_stasis = TransfersStasis(amid_client, ari.client, transfers_service, state_factory, state_persistor, config['uuid'])
        transfers_stasis.subscribe()

        state_factory.set_dependencies(amid_client, ari.client, transfers_service, state_persistor)

        api.add_resource(TransfersResource, '/transfers', resource_class_args=[transfers_service])
        api.add_resource(TransferResource, '/transfers/<transfer_id>', resource_class_args=[transfers_service])
        api.add_resource(TransferCompleteResource, '/transfers/<transfer_id>/complete', resource_class_args=[transfers_service])
