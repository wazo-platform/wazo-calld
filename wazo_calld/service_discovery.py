# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from wazo_calld.http_server import VERSION


# this function is not executed from the main thread
def self_check(config):
    port = config["rest_api"]["port"]
    scheme = "http"
    if config["rest_api"]["certificate"] and config["rest_api"]["private_key"]:
        scheme = "https"

    url = "{}://{}:{}/{}/status".format(scheme, "localhost", port, VERSION)
    try:
        response = requests.get(url, headers={'accept': 'application/json'}, verify=False)
        return response.status_code == 401
    except Exception:
        return False
