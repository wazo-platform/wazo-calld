# Copyright 2016-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import re

from requests import RequestException
from wazo_amid_client.exceptions import AmidProtocolError

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
        raise WazoAmidError(amid, e, {'original_parameters': parameters})


def unset_variable_ami(amid, channel_id, variable):
    set_variable_ami(amid, channel_id, variable, '')


def extension_exists(amid, context, exten, priority=1):
    try:
        response = amid.action('ShowDialplan', {'Context': context,
                                                'Extension': exten})
    except AmidProtocolError:
        return False
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


def record_start(amid, channel, filename, options=None):
    destination = {
        'Channel': channel,
        'File': filename,
    }
    if options:
        destination['options'] = options
    try:
        amid.action('MixMonitor', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def record_stop(amid, channel):
    destination = {
        'Channel': channel,
    }
    try:
        amid.action('StopMixMonitor', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def pause_queue_member(amid, interface):
    destination = {
        'Interface': interface,
        'Paused': True,
    }
    try:
        amid.action('QueuePause', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)


def unpause_queue_member(amid, interface):
    destination = {
        'Interface': interface,
        'Paused': False,
    }
    try:
        amid.action('QueuePause', destination)
    except RequestException as e:
        raise WazoAmidError(amid, e)
