# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.exceptions import APIException


class CallAlreadyInNode(APIException):

    def __init__(self, application_uuid, node_uuid, call_id):
        super(CallAlreadyInNode, self).__init__(
            status_code=400,
            message='Call already in node',
            error_id='call-already-in-node',
            details={
                'application_uuid': str(application_uuid),
                'node_uuid': str(node_uuid),
                'call_id': str(call_id),
            }
        )


class NoSuchApplication(APIException):

    def __init__(self, application_uuid):
        super(NoSuchApplication, self).__init__(
            status_code=404,
            message='No such application',
            error_id='no-such-application',
            details={
                'application_uuid': str(application_uuid),
            }
        )


class NoSuchCall(APIException):

    default_status_code = 404

    def __init__(self, call_id, status_code=None):
        status_code = status_code or self.default_status_code
        super(NoSuchCall, self).__init__(
            status_code=status_code,
            message='No such call',
            error_id='no-such-call',
            details={
                'call_id': call_id
            }
        )


class NoSuchMedia(APIException):

    def __init__(self, uri):
        super(NoSuchMedia, self).__init__(
            status_code=400,
            message='No such media',
            error_id='no-such-media',
            details={
                'uri': uri,
            }
        )


class NoSuchMoh(APIException):

    def __init__(self, uuid):
        super(NoSuchMoh, self).__init__(
            status_code=400,
            message='No such music on hold',
            error_id='no-such-moh',
            details={
                'uuid': str(uuid),
            }
        )


class NoSuchNode(APIException):

    def __init__(self, node_uuid):
        super(NoSuchNode, self).__init__(
            status_code=404,
            message='No such node',
            error_id='no-such-node',
            details={
                'node_uuid': str(node_uuid)
            }
        )


class NoSuchPlayback(APIException):

    def __init__(self, playback_uuid):
        super(NoSuchPlayback, self).__init__(
            status_code=404,
            message='No such playback',
            error_id='no-such-playback',
            details={
                'playback_uuid': str(playback_uuid)
            }
        )


class DeleteDestinationNode(APIException):

    def __init__(self, application_uuid, node_uuid):
        super(DeleteDestinationNode, self).__init__(
            status_code=400,
            message='Cannot delete destination node',
            error_id='delete-destination-node',
            details={
                'application_uuid': str(application_uuid),
                'node_uuid': str(node_uuid),
            }
        )
