# -*- coding: utf-8 -*-
# Copyright 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from xivo_ctid_ng.plugins.calls.services import CallsService
from .resources import UserVoicemailFolderResource
from .resources import UserVoicemailListenResource
from .resources import UserVoicemailMessageResource
from .resources import UserVoicemailRecordingResource
from .resources import UserVoicemailResource
from .resources import VoicemailFolderResource
from .resources import VoicemailListenResource
from .resources import VoicemailMessageResource
from .resources import VoicemailRecordingResource
from .resources import VoicemailResource
from .services import VoicemailsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        voicemails_service = VoicemailsService(ari.client, confd_client)
        # FIXME we should not instantiate an object from a different plugin, i.e. this is a hack
        calls_service = CallsService(amid_client, config['ari']['connection'], ari.client, confd_client)

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
        api.add_resource(VoicemailListenResource,
                         '/voicemails/<voicemail_id>/messages/<message_id>/listen',
                         resource_class_args=[calls_service, voicemails_service])
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
        api.add_resource(UserVoicemailListenResource,
                         '/users/me/voicemails/messages/<message_id>/listen',
                         resource_class_args=[auth_client, calls_service, voicemails_service])
