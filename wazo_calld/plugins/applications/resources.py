# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schema import (
    application_call_request_schema,
    application_call_schema,
    application_node_schema,
    application_playback_schema,
    application_schema,
    application_snoop_schema,
    application_snoop_put_schema,
)


class _BaseResource(AuthResource):

    def __init__(self, service):
        self._service = service


class ApplicationItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.read')
    def get(self, application_uuid):
        application = self._service.get_application(application_uuid)
        return application_schema.dump(application).data


class ApplicationCallItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.delete')
    def delete(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.delete_call(application_uuid, call_id)
        return '', 204


class ApplicationCallList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.create')
    def post(self, application_uuid):
        request_body = application_call_request_schema.load(request.get_json()).data
        application = self._service.get_application(application_uuid)
        call = self._service.originate(application, None, **request_body)
        return application_call_schema.dump(call).data, 201

    @required_acl('calld.applications.{application_uuid}.calls.read')
    def get(self, application_uuid):
        application = self._service.get_application(application_uuid)
        calls = self._service.list_calls(application)
        return {'items': application_call_schema.dump(calls, many=True).data}


class ApplicationCallHoldStartList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.hold.start.update')
    def put(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.start_call_hold(call_id)
        return '', 204


class ApplicationCallHoldStopList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.hold.stop.update')
    def put(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.stop_call_hold(call_id)
        return '', 204


class ApplicationCallMohStartList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.moh.{moh_uuid}.start.update')
    def put(self, application_uuid, call_id, moh_uuid):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.start_call_moh(call_id, moh_uuid)
        return '', 204


class ApplicationCallMohStopList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.moh.stop.update')
    def put(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.stop_call_moh(call_id)
        return '', 204


class ApplicationCallAnswerItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.answer.update')
    def put(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.call_answer(call_id)
        return '', 204


class ApplicationCallMuteStartList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.mute.start.update')
    def put(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.call_mute(application, call_id)
        return '', 204


class ApplicationCallMuteStopList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.mute.stop.update')
    def put(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        self._service.call_unmute(application, call_id)
        return '', 204


class ApplicationCallPlaybackList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.playbacks.create')
    def post(self, application_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_call_id(application, call_id)
        form = application_playback_schema.load(request.get_json()).data
        playback = self._service.create_playback(application_uuid, call_id, **form)
        return application_playback_schema.dump(playback).data


class ApplicationCallSnoopList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.calls.{call_id}.snoops.create')
    def post(self, application_uuid, call_id):
        form = application_snoop_schema.load(request.get_json()).data
        application = self._service.get_application(application_uuid)
        snoop = self._service.snoop_create(application, call_id, **form)
        return application_snoop_schema.dump(snoop).data, 201


class ApplicationPlaybackItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.playbacks.{playback_uuid}.delete')
    def delete(self, application_uuid, playback_uuid):
        self._service.get_application(application_uuid)
        # TODO: verify that playback_uuid is in the application
        self._service.delete_playback(application_uuid, playback_uuid)
        return '', 204


class ApplicationSnoopList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.snoops.read')
    def get(self, application_uuid):
        application = self._service.get_application(application_uuid)
        snoops = self._service.snoop_list(application)
        return {'items': application_snoop_schema.dump(snoops, many=True).data}


class ApplicationSnoopItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.snoops.{snoop_uuid}.read')
    def get(self, application_uuid, snoop_uuid):
        application = self._service.get_application(application_uuid)
        snoop = self._service.snoop_get(application, snoop_uuid)
        return application_snoop_schema.dump(snoop).data

    @required_acl('calld.applications.{application_uuid}.snoops.{snoop_uuid}.update')
    def put(self, application_uuid, snoop_uuid):
        form = application_snoop_put_schema.load(request.get_json()).data
        application = self._service.get_application(application_uuid)
        self._service.snoop_edit(application, snoop_uuid, form['whisper_mode'])
        return '', 204

    @required_acl('calld.applications.{application_uuid}.snoops.{snoop_uuid}.delete')
    def delete(self, application_uuid, snoop_uuid):
        application = self._service.get_application(application_uuid)
        self._service.snoop_delete(application, snoop_uuid)
        return '', 204


class ApplicationNodeCallItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.nodes.{node_uuid}.calls.{call_id}.delete')
    def delete(self, application_uuid, node_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_node_uuid(application, node_uuid)
        self._service.leave_node(application_uuid, node_uuid, [call_id])
        return '', 204

    @required_acl('calld.applications.{application_uuid}.nodes.{node_uuid}.calls.{call_id}.update')
    def put(self, application_uuid, node_uuid, call_id):
        application = self._service.get_application(application_uuid)
        self._service.get_node_uuid(application, node_uuid)
        self._service.join_node(application_uuid, node_uuid, [call_id], no_call_status_code=404)
        return '', 204


class ApplicationNodeCallList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.nodes.{node_uuid}.calls.create')
    def post(self, application_uuid, node_uuid):
        application = self._service.get_application(application_uuid)
        # TODO: Check if node is in application
        #       But Asterisk doesn't allow to create empty node in an application ...
        self._service.get_node(application, node_uuid, verify_application=False)
        request_body = application_call_request_schema.load(request.get_json()).data
        call = self._service.originate(application, node_uuid, **request_body)
        return application_call_schema.dump(call).data, 201


class ApplicationNodeItem(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.nodes.{node_uuid}.read')
    def get(self, application_uuid, node_uuid):
        application = self._service.get_application(application_uuid)
        node = self._service.get_node(application, node_uuid)
        return application_node_schema.dump(node).data

    @required_acl('calld.applications.{application_uuid}.nodes.{node_uuid}.delete')
    def delete(self, application_uuid, node_uuid):
        application = self._service.get_application(application_uuid)
        node = self._service.get_node(application, node_uuid)
        self._service.delete_node(application_uuid, node)
        return '', 204


class ApplicationNodeList(_BaseResource):

    @required_acl('calld.applications.{application_uuid}.nodes.read')
    def get(self, application_uuid):
        self._service.get_application(application_uuid)
        nodes = self._service.list_nodes(application_uuid)
        return {'items': application_node_schema.dump(nodes, many=True).data}

    @required_acl('calld.applications.{application_uuid}.nodes.create')
    def post(self, application_uuid):
        self._service.get_application(application_uuid)
        form = application_node_schema.load(request.get_json()).data
        call_ids = [call['id_'] for call in form.get('calls', [])]
        node = self._service.create_node_with_calls(application_uuid, call_ids)
        return application_node_schema.dump(node).data, 201
