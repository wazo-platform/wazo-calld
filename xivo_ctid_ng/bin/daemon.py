# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


import logging
import signal
import sys

from functools import partial

from xivo.daemonize import pidfile_context
from xivo.user_rights import change_user
from xivo import xivo_logging
from xivo_ctid_ng.controller import Controller
from xivo_ctid_ng.config import load as load_config

logger = logging.getLogger(__name__)


def main(argv):
    config = load_config(argv)

    if config['user']:
        change_user(config['user'])

    xivo_logging.setup_logging(config['log_filename'], config['foreground'], config['debug'], config['log_level'])
    xivo_logging.silence_loggers(['amqp', 'Flask-Cors', 'iso8601', 'kombu', 'swaggerpy', 'urllib3'], logging.WARNING)

    controller = Controller(config)
    signal.signal(signal.SIGTERM, partial(sigterm, controller))

    with pidfile_context(config['pid_filename'], config['foreground']):
        controller.run()


def sigterm(controller, signum, frame):
    controller.stop(reason='SIGTERM')


if __name__ == '__main__':
    main(sys.argv[1:])
