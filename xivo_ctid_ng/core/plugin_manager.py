# -*- coding: utf-8 -*-

# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

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
