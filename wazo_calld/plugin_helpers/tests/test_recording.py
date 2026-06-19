# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, patch

from ari.exceptions import ARINotFound

from ..recording import announce_active_recordings, play_record_start_announcement


def _make_channel(channel_id, record_active='1', start_sound='announcement-sound'):
    channel = Mock()
    channel.id = channel_id
    channel.json = {'channelvars': {'WAZO_CALL_RECORD_ACTIVE': record_active}}
    if start_sound is None:
        channel.getChannelVar.side_effect = ARINotFound(Mock(), Mock())
    else:
        channel.getChannelVar.return_value = {'value': start_sound}
    return channel


@patch('wazo_calld.plugin_helpers.recording.ami')
class TestPlayRecordStartAnnouncement(TestCase):
    def setUp(self):
        self.amid = Mock()

    def test_plays_configured_sound(self, mock_ami):
        channel = _make_channel('chan-1')

        play_record_start_announcement(self.amid, channel)

        mock_ami.play_beep.assert_called_once_with(
            self.amid, 'chan-1', 'announcement-sound'
        )

    def test_falls_back_to_beep_when_no_sound_configured(self, mock_ami):
        channel = _make_channel('chan-1', start_sound=None)

        play_record_start_announcement(self.amid, channel)

        mock_ami.play_beep.assert_called_once_with(self.amid, 'chan-1', 'beep')

    def test_falls_back_to_beep_when_sound_is_empty(self, mock_ami):
        channel = _make_channel('chan-1', start_sound='')

        play_record_start_announcement(self.amid, channel)

        mock_ami.play_beep.assert_called_once_with(self.amid, 'chan-1', 'beep')


@patch('wazo_calld.plugin_helpers.recording.ami')
class TestAnnounceActiveRecordings(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.amid = Mock()

    def test_announces_recorded_channels_only(self, mock_ami):
        recorded = _make_channel('chan-1')
        not_recorded = _make_channel('chan-2', record_active='0')
        self.ari.channels.get.side_effect = lambda channelId: {
            'chan-1': recorded,
            'chan-2': not_recorded,
        }[channelId]

        announce_active_recordings(self.ari, self.amid, ['chan-1', 'chan-2'])

        mock_ami.play_beep.assert_called_once_with(
            self.amid, 'chan-1', 'announcement-sound'
        )

    def test_skips_empty_channel_ids(self, mock_ami):
        announce_active_recordings(self.ari, self.amid, [None, ''])

        self.ari.channels.get.assert_not_called()
        mock_ami.play_beep.assert_not_called()

    def test_skips_missing_channels(self, mock_ami):
        self.ari.channels.get.side_effect = ARINotFound(Mock(), Mock())

        announce_active_recordings(self.ari, self.amid, ['chan-1'])

        mock_ami.play_beep.assert_not_called()
