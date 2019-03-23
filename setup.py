#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup
from setuptools import find_packages


setup(
    name='xivo-ctid-ng',
    version='2.0',
    description='Wazo CTI Server Daemon',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    url='http://wazo.community',
    packages=find_packages(),
    package_data={
        'xivo_ctid_ng.plugins': ['*/api.yml'],
    },
    entry_points={
        'console_scripts': [
            'xivo-ctid-ng=xivo_ctid_ng.bin.daemon:main',
        ],
        'xivo_ctid_ng.plugins': [
            'api = xivo_ctid_ng.plugins.api.plugin:Plugin',
            'applications = xivo_ctid_ng.plugins.applications.plugin:Plugin',
            'calls = xivo_ctid_ng.plugins.calls.plugin:Plugin',
            'conferences = xivo_ctid_ng.plugins.conferences.plugin:Plugin',
            'faxes = xivo_ctid_ng.plugins.faxes.plugin:Plugin',
            'relocates = xivo_ctid_ng.plugins.relocates.plugin:Plugin',
            'status = xivo_ctid_ng.plugins.status.plugin:Plugin',
            'switchboards = xivo_ctid_ng.plugins.switchboards.plugin:Plugin',
            'transfers = xivo_ctid_ng.plugins.transfers.plugin:Plugin',
            'voicemails = xivo_ctid_ng.plugins.voicemails.plugin:Plugin',
        ]
    }
)
