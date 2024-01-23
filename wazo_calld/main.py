# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import signal
import sys
from functools import partial

from xivo import xivo_logging
from xivo.config_helper import set_xivo_uuid
from xivo.user_rights import change_user

from wazo_calld.config import load as load_config
from wazo_calld.controller import Controller

logger = logging.getLogger(__name__)


def main(argv=None):
    argv = argv or sys.argv[1:]
    config = load_config(argv)

    if config['user']:
        change_user(config['user'])

    xivo_logging.setup_logging(
        config['log_filename'], debug=config['debug'], log_level=config['log_level']
    )
    xivo_logging.silence_loggers(
        [
            'amqp',
            'Flask-Cors',
            'iso8601',
            'kombu',
            'swaggerpy',
            'urllib3',
            'ari.model',
            'stevedore.extension',
        ],
        logging.WARNING,
    )
    if config['debug']:
        xivo_logging.silence_loggers(['swaggerpy'], logging.INFO)

    set_xivo_uuid(config, logger)

    controller = Controller(config)
    signal.signal(signal.SIGTERM, partial(_signal_handler, controller))
    signal.signal(signal.SIGINT, partial(_signal_handler, controller))

    controller.run()


def _signal_handler(controller, signum, frame):
    controller.stop(reason=signal.Signals(signum).name)


if __name__ == '__main__':
    main(sys.argv[1:])
