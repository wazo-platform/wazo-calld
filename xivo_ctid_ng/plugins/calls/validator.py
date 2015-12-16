# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from .exceptions import CallCreationError


def validate_originate_body(body):
    try:
        body['source']
        body['destination']
        body['source']['user']
        body['destination']['priority']
        body['destination']['extension']
        body['destination']['context']
    except KeyError as e:
        message = 'Missing key: "{key}"'.format(key=str(e))
        raise CallCreationError(message)
