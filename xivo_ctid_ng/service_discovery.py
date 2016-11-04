# -*- coding: utf-8 -*-
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

import requests


# this function is not executed from the main thread
def self_check(port, certificate):
    url = 'https://localhost:{}/1.0/status'.format(port)
    try:
        response = requests.get(url, headers={'accept': 'application/json'}, verify=certificate)
        return response.status_code == 401
    except Exception:
        return False
