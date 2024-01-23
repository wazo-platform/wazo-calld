#!/usr/bin/env python3
# Copyright 2021-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup

setup(
    name='wazo_calld_test_helpers',
    version='1.0.0',
    description='Wazo calld test helpers',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    packages=['wazo_calld_test_helpers'],
    package_dir={
        'wazo_calld_test_helpers': 'suite/helpers',
    },
)
