# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


import logging

from stevedore.named import NamedExtensionManager

logger = logging.getLogger(__name__)


def load_plugins(plugins, load_args=None, load_kwargs=None):
    load_args = load_args or []
    load_kwargs = load_kwargs or {}
    logger.debug('Enabled plugins: %s', plugins)
    plugins = NamedExtensionManager(namespace='xivo_ctid_ng.plugins',
                                    names=plugins,
                                    name_order=True,
                                    on_load_failure_callback=plugins_load_fail,
                                    propagate_map_exceptions=True,
                                    invoke_on_load=True)

    try:
        plugins.map(load_plugin, load_args, load_kwargs)
    except RuntimeError as e:
        logger.error("Could not load enabled plugins")
        logger.exception(e)


def load_plugin(ext, load_args, load_kwargs):
    logger.debug('Loading dynamic plugin: %s', ext.name)
    ext.obj.load(*load_args, **load_kwargs)


def plugins_load_fail(_, entrypoint, exception):
    logger.warning("There is an error with this module: %s", entrypoint)
    logger.warning('%s', exception)
