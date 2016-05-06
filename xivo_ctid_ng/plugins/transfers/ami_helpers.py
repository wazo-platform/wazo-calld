# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from requests import RequestException

from .exceptions import XiVOAmidUnreachable


def unset_variable_ami(amid, channel_id, variable):
    try:
        parameters = {'Channel': channel_id,
                      'Variable': variable,
                      'Value': ''}
        amid.action('Setvar', parameters)
    except RequestException as e:
        raise XiVOAmidUnreachable(amid, e)
