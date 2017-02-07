# -*- coding: utf-8 -*-

# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests


class ChanTest(object):
    def __init__(self, ari_config):
        self.config = ari_config

    def answer_channel(self, channel_id):
        url = '{base}/ari/chan_test/answer'.format(base=self.config['base_url'])
        params = {'id': channel_id}
        response = requests.post(url, params=params, auth=(self.config['username'], self.config['password']))
        response.raise_for_status()
