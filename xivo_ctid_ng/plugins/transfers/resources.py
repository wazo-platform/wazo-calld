# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import uuid

from flask import request

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.rest_api import AuthResource


class TransfersResource(AuthResource):

    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.transfers.create')
    def post(self):
        request_body = request.json
        recipient_call = self._transfers_service.create(request_body['transferred_call'],
                                                        request_body['initiator_call'],
                                                        request_body['context'],
                                                        request_body['exten'])
        result = {
            'uuid': str(uuid.uuid4()),
            'transferred_call': request_body['transferred_call'],
            'initiator_call': request_body['initiator_call'],
            'recipient_call': recipient_call,
            'context': request_body['context'],
            'exten': request_body['exten'],
        }
        return result, 201
