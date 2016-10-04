# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import logging

from ari.exceptions import ARINotFound, ARINotInStasis

from xivo_ctid_ng.core.exceptions import XiVOAmidError
from xivo_ctid_ng.helpers import ami

logger = logging.getLogger(__name__)


def is_in_stasis(ari, call_id):
    try:
        ari.channels.setChannelVar(channelId=call_id, variable='XIVO_TEST_STASIS')
        return True
    except ARINotInStasis:
        return False


def hold_transferred_call(ari, amid, transferred_call):
    ari.channels.mute(channelId=transferred_call, direction='in')
    ari.channels.hold(channelId=transferred_call)

    moh_class = 'default'
    try:
        moh_class_exists = ami.moh_class_exists(amid, moh_class)
    except XiVOAmidError:
        logger.error('xivo-amid could not tell if MOH "%s" exists. Assuming it does not.', moh_class)
        moh_class_exists = False

    if moh_class_exists:
        ari.channels.startMoh(channelId=transferred_call, mohClass=moh_class)
    else:
        ari.channels.startSilence(channelId=transferred_call)


def unhold_transferred_call(ari, transferred_call):
    ari.channels.unmute(channelId=transferred_call, direction='in')
    ari.channels.unhold(channelId=transferred_call)
    ari.channels.stopMoh(channelId=transferred_call)
    ari.channels.stopSilence(channelId=transferred_call)


def unring_initiator_call(ari, initiator_call):
    ari.channels.stopMoh(channelId=initiator_call)  # workaround for SCCP bug on ringStop
    ari.channels.ringStop(channelId=initiator_call)


def unset_variable(ari, amid, channel_id, variable):
    try:
        ari.channels.setChannelVar(channelId=channel_id, variable=variable, value='')
    except ARINotFound:
        pass
    except ARINotInStasis:
        ami.unset_variable_ami(amid, channel_id, variable)


def update_connectedline(ari, amid, channel_id, from_channel_id):
    from_channel = ari.channels.get(channelId=from_channel_id)
    name = from_channel.json['caller']['name']
    number = from_channel.json['caller']['number']
    ari.channels.setChannelVar(channelId=channel_id, variable='CONNECTEDLINE(name)', value=name.encode('utf-8'))
    ari.channels.setChannelVar(channelId=channel_id, variable='CONNECTEDLINE(num)', value=number.encode('utf-8'))


def set_bridge_variable(ari, bridge_id, variable, value):
    global_variable = 'XIVO_BRIDGE_VARIABLES_{}'.format(bridge_id)
    try:
        cache_str = ari.asterisk.getGlobalVar(variable=global_variable)['value']
    except ARINotFound:
        cache_str = '{}'
    if not cache_str:
        cache_str = '{}'
    cache = json.loads(cache_str)

    cache[variable] = value

    ari.asterisk.setGlobalVar(variable=global_variable, value=json.dumps(cache))


def get_bridge_variable(ari, bridge_id, variable):
    global_variable = 'XIVO_BRIDGE_VARIABLES_{}'.format(bridge_id)
    try:
        cache_str = ari.asterisk.getGlobalVar(variable=global_variable)['value']
    except ARINotFound:
        cache_str = '{}'
    if not cache_str:
        cache_str = '{}'
    cache = json.loads(cache_str)

    try:
        return cache[variable]
    except KeyError as e:
        raise ARINotFound(ari, e)


def convert_transfer_to_stasis(ari, amid, transferred_call, initiator_call, context, exten, transfer_id, variables):
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
    for channel_id, variable, value in set_variables:
        ari.channels.setChannelVar(channelId=channel_id, variable=variable, value=value, bypassStasis=True)

    ami.redirect(amid, transferred_call, context='convert_to_stasis', exten='transfer', extra_channel=initiator_call)
