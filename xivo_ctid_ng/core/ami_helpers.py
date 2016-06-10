# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from requests import RequestException

from .exceptions import XiVOAmidError

logger = logging.getLogger(__name__)


def set_variable_ami(amid, channel_id, variable, value):
    try:
        parameters = {'Channel': channel_id,
                      'Variable': variable,
                      'Value': value}
        amid.action('Setvar', parameters)
    except RequestException as e:
        raise XiVOAmidError(amid, e)


def unset_variable_ami(amid, channel_id, variable):
    set_variable_ami(amid, channel_id, variable, '')


def convert_transfer_to_stasis(amid, transferred_call, initiator_call, context, exten, transfer_id):
    set_variables = [(transferred_call, 'XIVO_TRANSFER_ROLE', 'transferred'),
                     (transferred_call, 'XIVO_TRANSFER_ID', transfer_id),
                     (transferred_call, 'XIVO_TRANSFER_RECIPIENT_CONTEXT', context),
                     (transferred_call, 'XIVO_TRANSFER_RECIPIENT_EXTEN', exten),
                     (initiator_call, 'XIVO_TRANSFER_ROLE', 'initiator'),
                     (initiator_call, 'XIVO_TRANSFER_ID', transfer_id),
                     (initiator_call, 'XIVO_TRANSFER_RECIPIENT_CONTEXT', context),
                     (initiator_call, 'XIVO_TRANSFER_RECIPIENT_EXTEN', exten)]
    try:
        for channel_id, variable, value in set_variables:
            parameters = {'Channel': channel_id,
                          'Variable': variable,
                          'Value': value}
            amid.action('Setvar', parameters)

        destination = {'Channel': transferred_call,
                       'ExtraChannel': initiator_call,
                       'Context': 'convert_to_stasis',
                       'Exten': 'transfer',
                       'Priority': 1}
        amid.action('Redirect', destination)
    except RequestException as e:
        raise XiVOAmidError(amid, e)


def extension_exists(amid, context, exten):
    try:
        response = amid.action('ShowDialplan', {'Context': context,
                                                'Extension': exten})
    except RequestException as e:
        raise XiVOAmidError(amid, e)

    return '1' in (event['Priority'] for event in response if event.get('Event') == 'ListDialplan')
