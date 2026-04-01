# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup

setup(
    name='call-logd-test-plugin',
    version='0.1',
    py_modules=['call_logd_test_plugin'],
    entry_points={
        'wazo_call_logd.plugins': [
            'tests = call_logd_test_plugin:Plugin',
        ],
    },
)
