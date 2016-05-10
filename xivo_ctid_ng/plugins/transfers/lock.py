import logging

from ari.exceptions import ARINotFound

from . import ari_helpers

logger = logging.getLogger(__name__)


class InvalidLock(ValueError):
    pass


class HangupLock(object):
    def __init__(self, ari, source_id, target_id):
        self._source_id = source_id
        self._target_id = target_id
        self._ari = ari

        if not self._is_valid_lock():
            raise InvalidLock()

    def _is_valid_lock(self):
        if not self._source_id:
            return False
        if not self._target_id:
            return False
        try:
            source_candidate_id = ari_helpers.get_bridge_variable(self._ari, self._target_id, 'XIVO_HANGUP_LOCK_SOURCE')
        except ARINotFound:
            return False
        return source_candidate_id == self._source_id

    @classmethod
    def from_source(cls, ari, source_id):
        result = []
        target_candidates = [bridge for bridge in ari.bridges.list()]
        for target_candidate in target_candidates:
            try:
                lock = cls(ari, source_id, target_candidate.id)
                result.append(lock)
            except InvalidLock:
                continue
        return result

    @classmethod
    def from_target(cls, ari, target_id):
        try:
            source_id = ari_helpers.get_bridge_variable(ari, target_id, 'XIVO_HANGUP_LOCK_SOURCE')
        except ARINotFound:
            raise InvalidLock()
        return cls(ari, source_id, target_id)

    def release(self):
        logger.debug('releasing hangup lock from source %s', self._source_id)
        self._clear()

    def kill_source(self):
        logger.debug('hanging up lock source %s', self._source_id)
        try:
            self._ari.channels.hangup(channelId=self._source_id)
        except ARINotFound:
            pass
        self._clear()

    def kill_target(self):
        try:
            target = self._ari.bridges.get(bridgeId=self._target_id)
        except ARINotFound:
            return
        if len(target.json['channels']) == 1:
            channel_id = target.json['channels'][0]
            try:
                self._ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                pass
        if len(target.json['channels']) <= 1:
            try:
                target.destroy()
            except ARINotFound:
                pass

        self._clear()

    def _clear(self):
        try:
            ari_helpers.set_bridge_variable(self._ari, self._target_id, 'XIVO_HANGUP_LOCK_SOURCE', '')
        except ARINotFound:
            pass
