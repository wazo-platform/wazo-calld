import sys

from flask import Flask, jsonify
from OpenSSL import SSL

app = Flask(__name__)

port = int(sys.argv[1])

context = SSL.Context(SSL.SSLv23_METHOD)
context.use_privatekey_file('/usr/local/share/xivo-auth-ssl/server.key')
context.use_certificate_file('/usr/local/share/xivo-auth-ssl/server.crt')

tokens = {'valid-token': 'uuid',
          'valid-token-1': 'uuid-1',
          'valid-token-2': 'uuid-2'}


@app.route("/0.1/token/valid-token", methods=['HEAD'])
@app.route("/0.1/token/valid-token-1", methods=['HEAD'])
@app.route("/0.1/token/valid-token-2", methods=['HEAD'])
def token_head():
    return '', 204


@app.route("/0.1/token/<token>", methods=['GET'])
def token_get(token):
    if token not in tokens:
        return '', 404

    return jsonify({
        'data': {
            'auth_id': tokens[token],
            'token': token
        }
    })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
