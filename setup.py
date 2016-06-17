#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from setuptools import setup
from setuptools import find_packages


setup(
    name='xivo-ctid-ng',
    version='2.0',
    description='XiVO CTI Server Daemon',
    author='Avencall',
    author_email='xivo-dev@lists.proformatique.com',
    url='http://www.xivo.io/',
    packages=find_packages(),
    package_data={
        'xivo_ctid_ng.plugins.api': ['*.json'],
    },
    scripts=['bin/xivo-ctid-ng'],
    entry_points={
        'xivo_ctid_ng.plugins': [
            'api = xivo_ctid_ng.plugins.api.plugin:Plugin',
            'calls = xivo_ctid_ng.plugins.calls.plugin:Plugin',
            'chats = xivo_ctid_ng.plugins.chats.plugin:Plugin',
            'transfers = xivo_ctid_ng.plugins.transfers.plugin:Plugin',
            'plugin_list = xivo_ctid_ng.plugins.plugin_list.plugin:Plugin',
        ]
    }
)
