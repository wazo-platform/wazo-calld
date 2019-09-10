# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import re

from requests import RequestException

from wazo_calld.exceptions import WazoAmidError

logger = logging.getLogger(__name__)

MOH_CLASS_RE = re.compile(r'^Class: (.+)$')


def set_variable_ami(amid, channel_id, variable, value):
    try:
        parameters = {'Channel': channel_id,
                      'Variable': variable,
                      'Value': value}
        amid.action('Setvar', parameters)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def unset_variable_ami(amid, channel_id, variable):
    set_variable_ami(amid, channel_id, variable, '')


def extension_exists(amid, context, exten, priority=1):
    try:
        response = amid.action('ShowDialplan', {'Context': context,
                                                'Extension': exten})
    except RequestException as e:
        raise WazoAmidError(amid, e)

    return str(priority) in (event['Priority'] for event in response if event.get('Event') == 'ListDialplan')


def moh_class_exists(amid, moh_class):
    try:
        response = amid.command('moh show classes')
    except RequestException as e:
        raise WazoAmidError(amid, e)

    raw_body = response['response']
    classes = [MOH_CLASS_RE.match(line).group(1) for line in raw_body if line.startswith('Class:')]
    return moh_class in classes


def redirect(amid, channel, context, exten, priority=1, extra_channel=None):
    destination = {
        'Channel': channel,
        'Context': context,
        'Exten': exten,
        'Priority': priority,
    }
    if extra_channel:
        destination['ExtraChannel'] = extra_channel
    try:
        amid.action('Redirect', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)
