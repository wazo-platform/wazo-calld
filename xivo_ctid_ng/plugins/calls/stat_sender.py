# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_bus.collectd.calls.event import CallAbandonedCollectdEvent
from xivo_bus.collectd.calls.event import CallConnectCollectdEvent
from xivo_bus.collectd.calls.event import CallDurationCollectdEvent
from xivo_bus.collectd.calls.event import CallEndCollectdEvent
from xivo_bus.collectd.calls.event import CallStartCollectdEvent

logger = logging.getLogger(__name__)


class StatSender(object):

    def __init__(self, collectd):
        self.collectd = collectd

    def new_call(self, call):
        logger.debug('sending stat for new call %s', call.channel.id)
        self.collectd.publish(CallStartCollectdEvent(call.app, call.app_instance))

    def abandoned(self, call):
        logger.debug('sending stat for abandoned call %s', call.channel.id)
        self.collectd.publish(CallAbandonedCollectdEvent(call.app, call.app_instance))

    def duration(self, call):
        logger.debug('sending stat for duration of call %s', call.channel.id)
        self.collectd.publish(CallDurationCollectdEvent(call.app, call.app_instance, call.duration()))

    def connect(self, call):
        logger.debug('sending stat for connecting call %s', call.channel.id)
        self.collectd.publish(CallConnectCollectdEvent(call.app, call.app_instance))

    def end_call(self, call):
        logger.debug('sending stat for ended call %s', call.channel.id)
        self.collectd.publish(CallEndCollectdEvent(call.app, call.app_instance))
