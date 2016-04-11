# -*- coding: UTF-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from .resources import TransferResource
from .resources import TransferCompleteResource
from .resources import TransfersResource
from .services import TransfersService
from .stasis import TransfersStasis
from .state_persistor import StatePersistor


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        state_persistor = StatePersistor(ari.client)

        transfers_service = TransfersService(ari.client, config['amid'], state_persistor)
        token_changed_subscribe(transfers_service.set_token)

        transfers_stasis = TransfersStasis(ari.client, transfers_service, state_persistor, config['uuid'])
        transfers_stasis.subscribe()

        api.add_resource(TransfersResource, '/transfers', resource_class_args=[transfers_service])
        api.add_resource(TransferResource, '/transfers/<transfer_id>', resource_class_args=[transfers_service])
        api.add_resource(TransferCompleteResource, '/transfers/<transfer_id>/complete', resource_class_args=[transfers_service])
