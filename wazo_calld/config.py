# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


import argparse

from xivo.chain_map import ChainMap
from xivo.config_helper import read_config_file_hierarchy, parse_config_file
from xivo.xivo_logging import get_log_level_by_name

_DEFAULT_HTTP_PORT = 9500
_DEFAULT_CONFIG = {
    'config_file': '/etc/wazo-calld/config.yml',
    'extra_config_files': '/etc/wazo-calld/conf.d/',
    'debug': False,
    'log_level': 'info',
    'log_filename': '/var/log/wazo-calld.log',
    'user': 'www-data',
    'rest_api': {
        'listen': '127.0.0.1',
        'port': _DEFAULT_HTTP_PORT,
        'certificate': None,
        'private_key': None,
        'cors': {
            'enabled': True,
            'allow_headers': ['Content-Type', 'X-Auth-Token', 'Wazo-Tenant'],
        },
    },
    'amid': {
        'host': 'localhost',
        'port': 9491,
        'prefix': None,
        'https': False,
    },
    'ari': {
        'connection': {
            'base_url': 'http://localhost:5039',
            'username': 'xivo',
            'password': 'opensesame',
        },
        'reconnection_delay': 10,
        'startup_connection_delay': 1,
    },
    'auth': {
        'host': 'localhost',
        'port': 9497,
        'prefix': None,
        'https': False,
        'key_file': '/var/lib/wazo-auth-keys/wazo-calld-key.yml',
    },
    'bus': {
        'username': 'guest',
        'password': 'guest',
        'host': 'localhost',
        'port': 5672,
        'exchange_name': 'xivo',
        'exchange_type': 'topic',
    },
    'collectd': {
        'exchange_name': 'collectd',
    },
    'confd': {
        'host': 'localhost',
        'port': 9486,
        'prefix': None,
        'https': False,
    },
    'phoned': {
        'host': 'localhost',
        'port': 9498,
        'prefix': None,
        'https': False,
    },
    'consul': {
        'host': 'localhost',
        'port': 8500,
        'scheme': 'http',
    },
    'service_discovery': {
        'enabled': True,
        'advertise_address': 'auto',
        'advertise_address_interface': 'eth0',
        'advertise_port': _DEFAULT_HTTP_PORT,
        'ttl_interval': 30,
        'refresh_interval': 27,
        'retry_interval': 2,
    },
    'remote_credentials': {
    },
    'enabled_plugins': {
        'adhoc_conferences': True,
        'api': True,
        'applications': True,
        'calls': True,
        'conferences': True,
        'config': True,
        'dial_mobile': True,
        'endpoints': True,
        'faxes': True,
        'meetings': True,
        'mobile': True,
        'relocates': True,
        'status': True,
        'switchboards': True,
        'transfers': True,
        'voicemails': True,
    },
    'max_meeting_participants': 25,
}


def load(argv):
    cli_config = _parse_cli_args(argv)
    file_config = read_config_file_hierarchy(ChainMap(cli_config, _DEFAULT_CONFIG))
    reinterpreted_config = _get_reinterpreted_raw_values(ChainMap(cli_config, file_config, _DEFAULT_CONFIG))
    service_key = _load_key_file(ChainMap(cli_config, file_config, _DEFAULT_CONFIG))
    return ChainMap(reinterpreted_config, cli_config, service_key, file_config, _DEFAULT_CONFIG)


def _parse_cli_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config-file',
                        action='store',
                        help="The path where is the config file. Default: %(default)s")
    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help="Log debug messages. Overrides log_level. Default: %(default)s")
    parser.add_argument('-l',
                        '--log-level',
                        action='store',
                        help="Logs messages with LOG_LEVEL details. Must be one of:\n"
                             "critical, error, warning, info, debug. Default: %(default)s")
    parser.add_argument('-u',
                        '--user',
                        action='store',
                        help="The owner of the process.")
    parsed_args = parser.parse_args(argv)

    result = {}
    if parsed_args.config_file:
        result['config_file'] = parsed_args.config_file
    if parsed_args.debug:
        result['debug'] = parsed_args.debug
    if parsed_args.log_level:
        result['log_level'] = parsed_args.log_level
    if parsed_args.user:
        result['user'] = parsed_args.user

    return result


def _load_key_file(config):
    key_file = parse_config_file(config['auth']['key_file'])
    return {'auth': {'username': key_file['service_id'],
                     'password': key_file['service_key']}}


def _get_reinterpreted_raw_values(config):
    result = {}

    log_level = config.get('log_level')
    if log_level:
        result['log_level'] = get_log_level_by_name(log_level)

    return result
