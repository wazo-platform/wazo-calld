# Copyright 2016-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import re

from requests import RequestException

from .exceptions import WazoAmidError

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


def get_variable_ami(amid, channel_id, variable):
    try:
        parameters = {'Channel': channel_id,
                      'Variable': variable}
        response = amid.action('Getvar', parameters)
    except RequestException as e:
        raise WazoAmidError(amid, e)

    for ami_response in response:
        if ami_response['Variable'] == variable:
            return ami_response['Value']
    return None


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


def redirect(amid, channel, context, exten, priority=1, extra_channel=None, extra_context=None, extra_exten=None, extra_priority=None):
    destination = {
        'Channel': channel,
        'Context': context,
        'Exten': exten,
        'Priority': priority,
    }
    if extra_channel:
        destination['ExtraChannel'] = extra_channel
    if extra_context:
        destination['ExtraContext'] = extra_context
    if extra_exten:
        destination['ExtraExten'] = extra_exten
        destination.setdefault('ExtraPriority', 1)
    if extra_priority:
        destination['ExtraPriority'] = extra_priority

    try:
        amid.action('Redirect', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def mute(amid, channel):
    destination = {
        'Channel': channel,
        'Direction': 'in',
        'State': 'on',
    }
    try:
        amid.action('MuteAudio', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def unmute(amid, channel):
    destination = {
        'Channel': channel,
        'Direction': 'in',
        'State': 'off',
    }
    try:
        amid.action('MuteAudio', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def dtmf(amid, channel, digit):
    destination = {
        'Channel': channel,
        'Digit': digit,
        'Receive': True,
    }
    try:
        amid.action('PlayDTMF', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def record_start(amid, channel):
    destination = {
        'Channel': channel,
        'File': get_variable_ami(amid, channel, 'XIVO_CALLRECORDFILE'),
    }
    try:
        amid.action('MixMonitor', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)
    set_variable_ami(amid, channel, 'WAZO_CALL_RECORD_ACTIVE', '1')


def record_stop(amid, channel):
    destination = {
        'Channel': channel,
    }
    try:
        amid.action('StopMixMonitor', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)
    set_variable_ami(amid, channel, 'WAZO_CALL_RECORD_ACTIVE', '0')
