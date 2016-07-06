# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import json
import sys

from flask import Flask, request

app = Flask(__name__)

port = int(sys.argv[1])

logging.basicConfig()
logger = logging.getLogger(__name__)

context = ('/usr/local/share/ssl/amid/server.crt', '/usr/local/share/ssl/amid/server.key')

action_response = ''


@app.route("/_set_action", methods=['POST'])
def set_action():
    global action_response
    action_response = request.get_json()
    logger.critical(action_response)

    return '', 204


@app.route("/1.0/action/<action>", methods=['POST'])
def action(action):
    logger.critical(action_response)
    return json.dumps(action_response), 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
