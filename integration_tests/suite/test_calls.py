# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from hamcrest import assert_that
from hamcrest import contains
from hamcrest import contains_inanyorder
from hamcrest import empty
from hamcrest import equal_to
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import contains_string

from .test_api.ari_ import MockApplication
from .test_api.ari_ import MockBridge
from .test_api.ari_ import MockChannel
from .test_api.base import IntegrationTest
from .test_api.confd import MockLine
from .test_api.confd import MockUser
from .test_api.confd import MockUserLine
from .test_api.constants import VALID_TOKEN


class TestListCalls(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestListCalls, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_list_calls_then_empty_list(self):
        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains()))

    def test_given_some_calls_and_no_user_id_when_list_calls_then_list_calls_with_no_user_uuid(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'user_uuid': None}),
            has_entries({'call_id': 'second-id',
                         'user_uuid': None}))))

    def test_given_some_calls_with_user_id_when_list_calls_then_list_calls_with_user_uuid(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': 'user1-uuid'},
                                       'second-id': {'XIVO_USERUUID': 'user2-uuid'}})
        self.confd.set_users(MockUser(uuid='user1-uuid'),
                             MockUser(uuid='user2-uuid'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'user_uuid': 'user1-uuid'}),
            has_entries({'call_id': 'second-id',
                         'user_uuid': 'user2-uuid'}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_status(self):
        self.ari.set_channels(MockChannel(id='first-id', state='Up'),
                              MockChannel(id='second-id', state='Ringing'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'status': 'Up'}),
            has_entries({'call_id': 'second-id',
                         'status': 'Ringing'}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_bridges(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.ari.set_bridges(MockBridge(id='first-bridge', channels=['first-id']),
                             MockBridge(id='second-bridge', channels=['second-id']))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'bridges': ['first-bridge']}),
            has_entries({'call_id': 'second-id',
                         'bridges': ['second-bridge']}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_talking_channels_and_users(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=['first-id', 'second-id']))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': 'user1-uuid'},
                                       'second-id': {'XIVO_USERUUID': 'user2-uuid'}})
        self.confd.set_users(MockUser(uuid='user1-uuid'),
                             MockUser(uuid='user2-uuid'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'talking_to': {'second-id': 'user2-uuid'}}),
            has_entries({'call_id': 'second-id',
                         'talking_to': {'first-id': 'user1-uuid'}}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_creation_time(self):
        self.ari.set_channels(MockChannel(id='first-id', creation_time='first-time'),
                              MockChannel(id='second-id', creation_time='second-time'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'creation_time': 'first-time'}),
            has_entries({'call_id': 'second-id',
                         'creation_time': 'second-time'}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_caller_id(self):
        self.ari.set_channels(MockChannel(id='first-id', caller_id_name='Weber', caller_id_number='4185556666'),
                              MockChannel(id='second-id', caller_id_name='Denis', caller_id_number='4185557777'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'caller_id_number': '4185556666',
                         'caller_id_name': 'Weber'}),
            has_entries({'call_id': 'second-id',
                         'caller_id_number': '4185557777',
                         'caller_id_name': 'Denis'}))))

    def test_given_some_calls_when_list_calls_by_application_then_list_of_calls_is_filtered(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'),
                              MockChannel(id='third-id'))
        self.ari.set_applications(MockApplication(name='my-app', channels=['first-id', 'third-id']))

        calls = self.ctid_ng.list_calls(application='my-app')

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}),
            has_entries({'call_id': 'third-id'}))))

    def test_given_some_calls_and_no_applications_when_list_calls_by_application_then_no_calls(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))

        calls = self.ctid_ng.list_calls(application='my-app', token=VALID_TOKEN)

        assert_that(calls, has_entry('items', empty()))

    def test_given_some_calls_when_list_calls_by_application_instance_then_list_of_calls_is_filtered(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'),
                              MockChannel(id='third-id'),
                              MockChannel(id='fourth-id'))
        self.ari.set_applications(MockApplication(name='my-app', channels=['first-id', 'second-id', 'third-id']))
        self.ari.set_global_variables({'XIVO_CHANNELS_first-id': json.dumps({'app': 'my-app',
                                                                             'app_instance': 'appX',
                                                                             'state': 'talking'}),
                                       'XIVO_CHANNELS_second-id': json.dumps({'app': 'my-app',
                                                                              'app_instance': 'appY',
                                                                              'state': 'talking'}),
                                       'XIVO_CHANNELS_third-id': json.dumps({'app': 'my-app',
                                                                             'app_instance': 'appX',
                                                                             'state': 'talking'})})

        calls = self.ctid_ng.list_calls(application='my-app', application_instance='appX')

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}),
            has_entries({'call_id': 'third-id'}))))


class TestGetCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestGetCall, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_get_call_then_404(self):
        call_id = 'not-found'

        result = self.ctid_ng.get_call_result(call_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_one_call_when_get_call_then_get_call(self):
        self.ari.set_channels(MockChannel(id='first-id', state='Up', creation_time='first-time', caller_id_name='Weber', caller_id_number='4185559999'),
                              MockChannel(id='second-id'))
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=['first-id', 'second-id']))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': 'user1-uuid'},
                                       'second-id': {'XIVO_USERUUID': 'user2-uuid'}})
        self.confd.set_users(MockUser(uuid='user1-uuid'),
                             MockUser(uuid='user2-uuid'))

        call = self.ctid_ng.get_call('first-id')

        assert_that(call, has_entries({
            'call_id': 'first-id',
            'user_uuid': 'user1-uuid',
            'status': 'Up',
            'talking_to': {
                'second-id': 'user2-uuid'
            },
            'bridges': contains('bridge-id'),
            'creation_time': 'first-time',
            'caller_id_name': 'Weber',
            'caller_id_number': '4185559999',
        }))


class TestDeleteCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestDeleteCall, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_delete_call_then_404(self):
        call_id = 'not-found'

        result = self.ctid_ng.delete_call_result(call_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_one_call_when_delete_call_then_call_hungup(self):
        call_id = 'call-id'
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))

        self.ctid_ng.hangup_call(call_id)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'DELETE',
            'path': '/ari/channels/call-id',
        }))))


class TestCreateCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCreateCall, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_create_call_with_correct_values(self):
        user_uuid = 'user-uuid'
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        self.ari.set_originates(MockChannel(id='new-call-id'))

        result = self.ctid_ng.originate(source=user_uuid,
                                        priority='my-priority',
                                        extension='my-extension',
                                        context='my-context')

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_when_create_call_then_ari_arguments_are_correct(self):
        user_uuid = 'user-uuid'
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        self.ari.set_originates(MockChannel('new-call-id'))

        self.ctid_ng.originate(source=user_uuid,
                               priority='my-priority',
                               extension='my-extension',
                               context='my-context',
                               variables={'MY_VARIABLE': 'my-value',
                                          'SECOND_VARIABLE': 'my-second-value'})

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', 'my-priority'],
                               ['extension', 'my-extension'],
                               ['context', 'my-context'],
                               ['endpoint', 'sip/line-name']),
            'json': has_entries({'variables': {'MY_VARIABLE': 'my-value',
                                               'SECOND_VARIABLE': 'my-second-value'}}),
        }))))

    def test_when_create_call_with_no_variables_then_ari_variables_are_empty(self):
        user_uuid = 'user-uuid'
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        self.ari.set_originates(MockChannel(id='new-call-id'))

        self.ctid_ng.originate(source=user_uuid,
                               priority='my-priority',
                               extension='my-extension',
                               context='my-context')

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'json': has_entries({'variables': {}}),
        }))))

    def test_create_call_with_multiple_lines(self):
        user_uuid = 'user-uuid'
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id2', main_line=False),
                                                 MockUserLine('line-id', main_line=True)]})
        self.ari.set_originates(MockChannel(id='new-call-id'))

        result = self.ctid_ng.originate(source=user_uuid,
                                        priority='my-priority',
                                        extension='my-extension',
                                        context='my-context')

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_create_call_with_no_lines(self):
        user_uuid = 'user-uuid'
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_user_lines({'user-uuid': []})

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               priority='my-priority',
                                               extension='my-extension',
                                               context='my-context',
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('line')))

    def test_create_call_with_invalid_user(self):
        user_uuid = 'user-uuid-not-found'

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               priority='my-priority',
                                               extension='my-extension',
                                               context='my-context', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('user')))

    def test_create_call_with_missing_source(self):
        body = {'destination': {'priority': '1',
                                'extension': 'myexten',
                                'context': 'mycontext'}}
        result = self.ctid_ng.post_call_raw(body, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('source')))

    def test_create_call_with_no_content_type(self):
        user_uuid = 'user-uuid'
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        self.ari.set_originates(MockChannel(id='new-call-id'))

        with self.ctid_ng.send_no_content_type():
            result = self.ctid_ng.post_call_result(source=user_uuid,
                                                   priority='my-priority',
                                                   extension='my-extension',
                                                   context='my-context',
                                                   token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(201), result.json())


class TestNoConfd(IntegrationTest):

    asset = 'no_confd'

    def setUp(self):
        super(TestNoConfd, self).setUp()
        self.ari.reset()

    def test_given_no_confd_when_originate_then_503(self):
        result = self.ctid_ng.post_call_result(source='user-uuid',
                                               priority=None,
                                               extension=None,
                                               context=None,
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_confd_when_connect_user_then_503(self):
        result = self.ctid_ng.put_call_user_result(call_id='call-id',
                                                   user_uuid='user-uuid',
                                                   token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))


class TestFailingARI(IntegrationTest):

    asset = 'failing_ari'

    def setUp(self):
        super(TestFailingARI, self).setUp()
        self.confd.reset()

    def test_given_no_ari_when_list_calls_then_503(self):
        result = self.ctid_ng.get_calls_result(token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_ari_when_get_call_then_503(self):
        result = self.ctid_ng.get_call_result('first-id', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_ari_when_originate_then_503(self):
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        result = self.ctid_ng.post_call_result(source='user-uuid',
                                               priority='priority',
                                               extension='extension',
                                               context='context',
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_ari_when_delete_call_then_503(self):
        result = self.ctid_ng.delete_call_result('call-id', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))


class TestConnectUser(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestConnectUser, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_one_call_and_one_user_when_connect_user_then_the_two_are_talking(self):
        self.ari.set_channels(MockChannel(id='call-id'),
                              MockChannel(id='new-call-id', ))
        self.ari.set_channel_variable({'new-call-id': {'XIVO_USERUUID': 'user-uuid'}})
        self.ari.set_global_variables({'XIVO_CHANNELS_call-id': json.dumps({'app': 'sw',
                                                                            'app_instance': 'sw1',
                                                                            'state': 'ringing'})})
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})
        self.ari.set_originates(MockChannel(id='new-call-id'))

        new_call = self.ctid_ng.connect_user('call-id', 'user-uuid')

        assert_that(new_call, has_entries({
            'call_id': 'new-call-id'
        }))
        assert_that(self.ari.requests(), has_entry('requests', has_items(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': contains_inanyorder(['app', 'callcontrol'], ['endpoint', 'sip/line-name'], ['appArgs', 'sw1,dialed_from,call-id']),
        }))))

    def test_given_no_user_when_connect_user_then_400(self):
        self.ari.set_channels(MockChannel(id='call-id'))

        result = self.ctid_ng.put_call_user_result('call-id', 'user-uuid', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('user')))

    def test_given_user_has_no_line_when_connect_user_then_400(self):
        self.ari.set_channels(MockChannel(id='call-id'))
        self.confd.set_users(MockUser(uuid='user-uuid'))

        result = self.ctid_ng.put_call_user_result('call-id', 'user-uuid', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('user')))

    def test_given_no_call_when_connect_user_then_404(self):
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.confd.set_user_lines({'user-uuid': [MockUserLine('line-id')]})

        result = self.ctid_ng.put_call_user_result('call-id', 'user-uuid', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json(), has_entry('message', contains_string('call')))
