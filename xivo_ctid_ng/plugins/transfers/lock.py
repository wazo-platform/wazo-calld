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
        try:
            source_candidate_id = ari_helpers.get_bridge_variable(self._ari, self._target_id, 'XIVO_HANGUP_LOCK_SOURCE')
        except ARINotFound:
            return False
        return source_candidate_id == self._source_id

    def release(self):
        logger.debug('releasing hangup lock from source %s', self._source_id)
        ari_helpers.set_bridge_variable(self._ari, self._target_id, 'XIVO_HANGUP_LOCK_SOURCE', '')
