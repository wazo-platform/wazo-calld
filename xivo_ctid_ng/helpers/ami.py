# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import json
import re

from requests import RequestException

from xivo_ctid_ng.core.exceptions import XiVOAmidError

logger = logging.getLogger(__name__)

MOH_CLASS_RE = re.compile(r'^Class: (.+)$')


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


def convert_transfer_to_stasis(amid, transferred_call, initiator_call, context, exten, transfer_id, variables):
    channel_variables = json.dumps(variables) if variables else '{}'
    set_variables = [(transferred_call, 'XIVO_TRANSFER_ROLE', 'transferred'),
                     (transferred_call, 'XIVO_TRANSFER_ID', transfer_id),
                     (transferred_call, 'XIVO_TRANSFER_RECIPIENT_CONTEXT', context),
                     (transferred_call, 'XIVO_TRANSFER_RECIPIENT_EXTEN', exten),
                     (initiator_call, 'XIVO_TRANSFER_ROLE', 'initiator'),
                     (initiator_call, 'XIVO_TRANSFER_ID', transfer_id),
                     (initiator_call, 'XIVO_TRANSFER_RECIPIENT_CONTEXT', context),
                     (initiator_call, 'XIVO_TRANSFER_RECIPIENT_EXTEN', exten),
                     (initiator_call, 'XIVO_TRANSFER_VARIABLES', channel_variables)]
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


def extension_exists(amid, context, exten, priority=1):
    try:
        response = amid.action('ShowDialplan', {'Context': context,
                                                'Extension': exten})
    except RequestException as e:
        raise XiVOAmidError(amid, e)

    return str(priority) in (event['Priority'] for event in response if event.get('Event') == 'ListDialplan')


def moh_class_exists(amid, moh_class):
    try:
        response = amid.command('moh show classes')
    except RequestException as e:
        raise XiVOAmidError(amid, e)

    raw_body = response['response']
    classes = [MOH_CLASS_RE.match(line).group(1) for line in raw_body if line.startswith('Class:')]
    return moh_class in classes
