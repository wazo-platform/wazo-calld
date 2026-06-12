# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound

from . import ami

logger = logging.getLogger(__name__)

DEFAULT_RECORD_BEEP = 'beep'


def play_record_start_announcement(amid, channel):
    try:
        announcement = channel.getChannelVar(variable='WAZO_RECORDING_START_SOUND')[
            'value'
        ]
    except ARINotFound:
        announcement = None
    ami.play_beep(amid, channel.id, announcement or DEFAULT_RECORD_BEEP)


def announce_active_recordings(ari, amid, channel_ids):
    for channel_id in channel_ids:
        if not channel_id:
            continue
        try:
            channel = ari.channels.get(channelId=channel_id)
        except ARINotFound:
            continue
        if channel.json['channelvars'].get('WAZO_CALL_RECORD_ACTIVE') != '1':
            continue
        logger.debug(
            'replaying recording start announcement for channel %s', channel_id
        )
        play_record_start_announcement(amid, channel)
