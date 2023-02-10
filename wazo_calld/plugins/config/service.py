# Copyright 2021-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading


class ConfigService:
    # Changing root logger log-level requires application-wide lock.
    # This lock will be shared across all instances.
    _lock = threading.Lock()

    def __init__(self, config):
        self._config = dict(config)
        self._enabled = False

    def get_config(self):
        with self._lock:
            return dict(self._config)

    def update_config(self, config):
        with self._lock:
            self._update_debug(config['debug'])
            self._config['debug'] = config['debug']

    def _update_debug(self, debug):
        if debug:
            self._enable_debug()
        else:
            self._disable_debug()

    def _enable_debug(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

    def _disable_debug(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(self._config['log_level'])
