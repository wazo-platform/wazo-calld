#!/usr/bin/env python3
# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

_transcriptions: list[dict] = []
_requests: list = []


def _reset() -> None:
    global _requests
    global _transcriptions
    _requests = []
    _transcriptions = []


@app.before_request
def log_request():
    global _requests

    if request.path.startswith('/_'):
        return

    log = {
        'method': request.method,
        'path': request.path,
        'query': list(request.args.items(multi=True)),
        'body': request.data.decode('utf-8'),
        'json': request.json if request.is_json else None,
        'headers': dict(request.headers),
    }
    _requests.append(log)


@app.route('/_reset', methods=['POST'])
def reset():
    _reset()
    return '', 204


@app.route('/_requests', methods=['GET'])
def list_requests():
    return jsonify({'requests': _requests})


@app.route('/_set_transcriptions', methods=['POST'])
def set_transcriptions():
    global _transcriptions
    _transcriptions = request.get_json().get('transcriptions', [])
    return '', 204


@app.route('/1.0/voicemails/transcriptions', methods=['GET'])
def list_transcriptions():
    voicemail_id_param = request.args.get('voicemail_id', '')
    voicemail_ids = set()
    if voicemail_id_param:
        for v in voicemail_id_param.split(','):
            v = v.strip()
            if v:
                try:
                    voicemail_ids.add(int(v))
                except ValueError:
                    pass

    if voicemail_ids:
        items = [t for t in _transcriptions if t.get('voicemail_id') in voicemail_ids]
    else:
        items = list(_transcriptions)

    return jsonify(
        {
            'items': items,
            'total': len(items),
            'filtered': len(items),
        }
    )


if __name__ == "__main__":
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
