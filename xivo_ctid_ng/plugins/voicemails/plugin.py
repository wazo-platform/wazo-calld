# -*- coding: utf-8 -*-
# Copyright 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .bus_consume import VoicemailsBusEventHandler
from .resources import UserVoicemailFolderResource
from .resources import UserVoicemailMessageResource
from .resources import UserVoicemailRecordingResource
from .resources import UserVoicemailResource
from .resources import VoicemailFolderResource
from .resources import VoicemailMessageResource
from .resources import VoicemailRecordingResource
from .resources import VoicemailResource
from .services import VoicemailsService
from .storage import new_cache
from .storage import new_filesystem_storage

logger = logging.getLogger(__name__)


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(confd_client.set_token)

        voicemail_storage = new_filesystem_storage()
        voicemail_cache = new_cache(voicemail_storage)
        try:
            voicemail_cache.refresh_cache()
        except Exception:
            logger.exception('fail to refresh voicemail cache')
        voicemails_service = VoicemailsService(ari.client, confd_client, voicemail_storage)

        voicemails_bus_event_handler = VoicemailsBusEventHandler(confd_client, bus_publisher, voicemail_cache)
        voicemails_bus_event_handler.subscribe(bus_consumer)

        api.add_resource(VoicemailResource,
                         '/voicemails/<voicemail_id>',
                         resource_class_args=[voicemails_service])
        api.add_resource(VoicemailFolderResource,
                         '/voicemails/<voicemail_id>/folders/<folder_id>',
                         resource_class_args=[voicemails_service])
        api.add_resource(VoicemailMessageResource,
                         '/voicemails/<voicemail_id>/messages/<message_id>',
                         resource_class_args=[voicemails_service])
        api.add_resource(VoicemailRecordingResource,
                         '/voicemails/<voicemail_id>/messages/<message_id>/recording',
                         resource_class_args=[voicemails_service])
        api.add_resource(UserVoicemailResource,
                         '/users/me/voicemails',
                         resource_class_args=[auth_client, voicemails_service])
        api.add_resource(UserVoicemailFolderResource,
                         '/users/me/voicemails/folders/<folder_id>',
                         resource_class_args=[auth_client, voicemails_service])
        api.add_resource(UserVoicemailMessageResource,
                         '/users/me/voicemails/messages/<message_id>',
                         resource_class_args=[auth_client, voicemails_service])
        api.add_resource(UserVoicemailRecordingResource,
                         '/users/me/voicemails/messages/<message_id>/recording',
                         resource_class_args=[auth_client, voicemails_service])
