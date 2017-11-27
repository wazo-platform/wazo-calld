# -*- coding: utf-8 -*-
# Copyright 2015-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json

from hamcrest import all_of
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
from xivo_test_helpers import until

from .helpers.ari_ import MockApplication
from .helpers.ari_ import MockBridge
from .helpers.ari_ import MockChannel
from .helpers.auth import MockUserToken
from .helpers.base import IntegrationTest
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import MockLine
from .helpers.confd import MockUser
from .helpers.constants import VALID_TOKEN
from .helpers.wait_strategy import CtidNgUpWaitStrategy

SOME_LOCAL_CHANNEL_NAME = 'Local/channel'
SOME_PRIORITY = 1


class TestListCalls(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestListCalls, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_list_calls_then_empty_list(self):
        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains()))

    def test_given_some_calls_with_user_id_when_list_calls_then_calls_are_complete(self):
        self.ari.set_channels(MockChannel(id='first-id',
                                          caller_id_name='Weber',
                                          caller_id_number='4185556666',
                                          connected_line_name='Denis',
                                          connected_line_number='4185557777',
                                          creation_time='first-time',
                                          state='Up'),
                              MockChannel(id='second-id',
                                          caller_id_name='Denis',
                                          caller_id_number='4185557777',
                                          connected_line_name='Weber',
                                          connected_line_number='4185556666',
                                          creation_time='second-time',
                                          state='Ringing'))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': 'user1-uuid',
                                                    'WAZO_CHANNEL_DIRECTION': 'to-wazo'},
                                       'second-id': {'XIVO_USERUUID': 'user2-uuid',
                                                     'WAZO_CHANNEL_DIRECTION': 'from-wazo'}})
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=['first-id', 'second-id']))
        self.confd.set_users(MockUser(uuid='user1-uuid'),
                             MockUser(uuid='user2-uuid'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'user_uuid': 'user1-uuid',
                         'status': 'Up',
                         'bridges': ['bridge-id'],
                         'talking_to': {'second-id': 'user2-uuid'},
                         'creation_time': 'first-time',
                         'caller_id_number': '4185556666',
                         'caller_id_name': 'Weber',
                         'peer_caller_id_number': '4185557777',
                         'peer_caller_id_name': 'Denis',
                         'is_caller': True}),
            has_entries({'call_id': 'second-id',
                         'user_uuid': 'user2-uuid',
                         'status': 'Ringing',
                         'bridges': ['bridge-id'],
                         'talking_to': {'first-id': 'user1-uuid'},
                         'creation_time': 'second-time',
                         'caller_id_number': '4185557777',
                         'caller_id_name': 'Denis',
                         'peer_caller_id_number': '4185556666',
                         'peer_caller_id_name': 'Weber',
                         'is_caller': False}))))

    def test_given_some_calls_and_no_user_id_when_list_calls_then_list_calls_with_no_user_uuid(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'user_uuid': None}),
            has_entries({'call_id': 'second-id',
                         'user_uuid': None}))))

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

    def test_given_some_calls_and_application_bound_to_all_channels_when_list_calls_by_application_then_all_calls(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.ari.set_applications(MockApplication(name='my-app', channels=['__AST_CHANNEL_ALL_TOPIC']))

        calls = self.ctid_ng.list_calls(application='my-app')

        assert_that(calls,
                    has_entry('items', contains_inanyorder(
                        has_entries({'call_id': 'first-id'}),
                        has_entries({'call_id': 'second-id'}))))

    def test_given_some_calls_and_application_bound_to_all_channels_when_list_calls_by_application_instance_then_calls_are_still_filtered_by_application(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.ari.set_global_variables({'XIVO_CHANNELS_first-id': json.dumps({'app': 'my-app',
                                                                             'app_instance': 'appX',
                                                                             'state': 'talking'}),
                                       'XIVO_CHANNELS_second-id': json.dumps({'app': 'another-app',
                                                                              'app_instance': 'appX',
                                                                              'state': 'talking'})})
        self.ari.set_applications(MockApplication(name='my-app', channels=['__AST_CHANNEL_ALL_TOPIC']))

        calls = self.ctid_ng.list_calls(application='my-app', application_instance='appX', token=VALID_TOKEN)

        assert_that(calls, has_entry('items', contains(
            has_entries({'call_id': 'first-id'}))))

    def test_given_local_channels_when_list_then_talking_to_is_none(self):
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id', name=SOME_LOCAL_CHANNEL_NAME))
        self.ari.set_bridges(MockBridge(id='bridge-id', channels=['first-id', 'second-id']))
        self.confd.set_users(MockUser(uuid='user1-uuid'),
                             MockUser(uuid='user2-uuid'))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': 'user1-uuid'},
                                       'second-id': {'XIVO_USERUUID': 'user2-uuid'}})

        calls = self.ctid_ng.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'talking_to': {'second-id': None}}),
            has_entries({'call_id': 'second-id',
                         'talking_to': {'first-id': 'user1-uuid'}}))))


class TestUserListCalls(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestUserListCalls, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_list_calls_then_empty_list(self):
        token = 'my-token'
        user_uuid = 'user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        calls = self.ctid_ng.list_my_calls(token=token)

        assert_that(calls, has_entry('items', contains()))

    def test_given_some_calls_with_user_id_when_list_my_calls_then_calls_are_filtered_by_user(self):
        token = 'my-token'
        user_uuid = 'user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.ari.set_channels(MockChannel(id='my-call'),
                              MockChannel(id='my-second-call'),
                              MockChannel(id='others-call'),
                              MockChannel(id='no-user-call'))
        self.ari.set_channel_variable({'my-call': {'XIVO_USERUUID': user_uuid},
                                       'my-second-call': {'XIVO_USERUUID': user_uuid},
                                       'others-call': {'XIVO_USERUUID': 'user2-uuid'}})
        self.confd.set_users(MockUser(uuid=user_uuid),
                             MockUser(uuid='user2-uuid'))

        calls = self.ctid_ng.list_my_calls(token=token)

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'my-call',
                         'user_uuid': user_uuid}),
            has_entries({'call_id': 'my-second-call',
                         'user_uuid': user_uuid}))))

    def test_given_some_calls_when_list_calls_by_application_then_list_of_calls_is_filtered(self):
        token = 'my-token'
        user_uuid = 'user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'),
                              MockChannel(id='third-id'))
        self.ari.set_applications(MockApplication(name='my-app', channels=['first-id', 'third-id']))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': user_uuid},
                                       'second-id': {'XIVO_USERUUID': user_uuid},
                                       'third-id': {'XIVO_USERUUID': user_uuid}})

        calls = self.ctid_ng.list_my_calls(application='my-app', token=token)

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}),
            has_entries({'call_id': 'third-id'}))))

    def test_given_some_calls_and_no_applications_when_list_calls_by_application_then_no_calls(self):
        token = 'my-token'
        user_uuid = 'user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': user_uuid},
                                       'second-id': {'XIVO_USERUUID': user_uuid}})

        calls = self.ctid_ng.list_my_calls(application='my-app', token=token)

        assert_that(calls, has_entry('items', empty()))

    def test_given_some_calls_when_list_calls_by_application_instance_then_list_of_calls_is_filtered(self):
        token = 'my-token'
        user_uuid = 'user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'),
                              MockChannel(id='third-id'),
                              MockChannel(id='fourth-id'))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': user_uuid},
                                       'second-id': {'XIVO_USERUUID': user_uuid},
                                       'third-id': {'XIVO_USERUUID': user_uuid},
                                       'fourth-id': {'XIVO_USERUUID': user_uuid}})
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

        calls = self.ctid_ng.list_my_calls(application='my-app', application_instance='appX', token=token)

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}),
            has_entries({'call_id': 'third-id'}))))

    def test_given_local_channels_when_list_then_local_channels_are_ignored(self):
        token = 'my-token'
        user_uuid = 'user-uuid'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.ari.set_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id', name=SOME_LOCAL_CHANNEL_NAME))
        self.ari.set_channel_variable({'first-id': {'XIVO_USERUUID': user_uuid},
                                       'second-id': {'XIVO_USERUUID': user_uuid}})

        calls = self.ctid_ng.list_my_calls(token=token)

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}))))


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


class TestUserDeleteCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestUserDeleteCall, self).setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_calls_when_delete_call_then_404(self):
        call_id = 'not-found'
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))

        result = self.ctid_ng.delete_user_me_call_result(call_id, token=token)

        assert_that(result.status_code, equal_to(404))

    def test_given_another_call_when_delete_call_then_403(self):
        call_id = 'call-id'
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))
        self.ari.set_channel_variable({call_id: {'XIVO_USERUUID': 'some-other-uuid'}})

        result = self.ctid_ng.delete_user_me_call_result(call_id, token=token)

        assert_that(result.status_code, equal_to(403))
        assert_that(result.json(), has_entry('message', contains_string('user')))

    def test_given_my_call_when_delete_call_then_call_hungup(self):
        call_id = 'call-id'
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))
        self.ari.set_channel_variable({call_id: {'XIVO_USERUUID': user_uuid}})

        self.ctid_ng.hangup_my_call(call_id, token)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'DELETE',
            'path': '/ari/channels/call-id',
        }))))

    def test_local_channel_when_delete_call_then_call_hungup(self):
        call_id = 'call-id'
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid))
        self.ari.set_channels(MockChannel(id=call_id, state='Up', name=SOME_LOCAL_CHANNEL_NAME))
        self.ari.set_channel_variable({call_id: {'XIVO_USERUUID': user_uuid}})

        result = self.ctid_ng.delete_user_me_call_result(call_id, token=token)

        assert_that(result.status_code, equal_to(404))


class TestCreateCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCreateCall, self).setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_create_call_with_correct_values(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        result = self.ctid_ng.originate(source=user_uuid,
                                        priority=priority,
                                        extension='my-extension',
                                        context='my-context')

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_when_create_call_then_ari_arguments_are_correct(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel('new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        self.ctid_ng.originate(source=user_uuid,
                               priority=priority,
                               extension='my-extension',
                               context='my-context',
                               variables={'MY_VARIABLE': 'my-value',
                                          'SECOND_VARIABLE': 'my-second-value',
                                          'CONNECTEDLINE(name)': 'my-connected-line',
                                          'XIVO_FIX_CALLERID': '1'})

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', str(priority)],
                               ['extension', 'my-extension'],
                               ['context', 'my-context'],
                               ['endpoint', 'sip/line-name']),
            'json': has_entries({'variables': has_entries({'MY_VARIABLE': 'my-value',
                                                           'SECOND_VARIABLE': 'my-second-value',
                                                           'CALLERID(name)': 'my-extension',
                                                           'CALLERID(num)': 'my-extension',
                                                           'CONNECTEDLINE(name)': 'my-connected-line',
                                                           'CONNECTEDLINE(num)': 'my-extension',
                                                           'XIVO_FIX_CALLERID': '1'})}),
        }))))

    def test_when_create_call_with_no_variables_then_default_variables_are_set(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        self.ctid_ng.originate(source=user_uuid,
                               priority=priority,
                               extension='my-extension',
                               context='my-context')

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'json': has_entries({'variables': {'CONNECTEDLINE(num)': 'my-extension',
                                               'CONNECTEDLINE(name)': 'my-extension',
                                               'CALLERID(name)': 'my-extension',
                                               'CALLERID(num)': 'my-extension',
                                               'XIVO_FIX_CALLERID': '1'}}),
        }))))

    def test_when_create_call_with_pound_exten_then_connected_line_num_is_empty(self):
        '''
        This is a workaround for chan-sip bug that does not SIP-encode the pound sign
        in the SIP header To, causing Aastra phones to reject the INVITE.
        '''

        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', '#pound', priority)

        self.ctid_ng.originate(source=user_uuid,
                               priority=priority,
                               extension='#pound',
                               context='my-context')

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'json': has_entries({'variables': {'CONNECTEDLINE(num)': '',
                                               'CONNECTEDLINE(name)': '#pound',
                                               'CALLERID(name)': '#pound',
                                               'CALLERID(num)': '#pound',
                                               'XIVO_FIX_CALLERID': '1'}}),
        }))))

    def test_create_call_with_multiple_lines(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id', 'line-id2']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        result = self.ctid_ng.originate(source=user_uuid,
                                        priority=priority,
                                        extension='my-extension',
                                        context='my-context')

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_create_call_when_no_confd_then_503(self):
        priority = 1
        self.amid.set_valid_exten('my-context', 'my-extension', priority)
        with self.confd_stopped():
            result = self.ctid_ng.post_call_result(source='user-uuid',
                                                   priority=priority,
                                                   extension='my-extension',
                                                   context='my-context',
                                                   token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_create_call_with_no_lines(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_user_lines({'user-uuid': []})
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               priority=priority,
                                               extension='my-extension',
                                               context='my-context',
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('line')))

    def test_create_call_with_invalid_user(self):
        user_uuid = 'user-uuid-not-found'
        priority = 1
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               priority=priority,
                                               extension='my-extension',
                                               context='my-context', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('user')))

    def test_create_call_with_missing_source(self):
        self.amid.set_valid_exten('mycontext', 'myexten')
        body = {'destination': {'priority': '1',
                                'extension': 'myexten',
                                'context': 'mycontext'}}
        result = self.ctid_ng.post_call_raw(body, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('details', has_item('source')))

    def test_create_call_with_wrong_exten(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_no_valid_exten()

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               priority=priority,
                                               extension='not-found',
                                               context='my-context',
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('details', has_item('exten')))

    def test_create_call_with_no_content_type(self):
        user_uuid = 'user-uuid'
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        with self.ctid_ng.send_no_content_type():
            result = self.ctid_ng.post_call_result(source=user_uuid,
                                                   priority=priority,
                                                   extension='my-extension',
                                                   context='my-context',
                                                   token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(201), result.json())

    def test_create_call_with_explicit_line_not_found(self):
        user_uuid = 'user-uuid'
        line_id_not_found = 999999999999999999
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['first-line-id']))
        self.confd.set_lines(MockLine(id='first-line-id', name='first-line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               line_id=line_id_not_found,
                                               priority=priority,
                                               extension='my-extension',
                                               context='my-context',
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'], contains_string('line'))

    def test_create_call_with_explicit_wrong_line(self):
        user_uuid = 'user-uuid'
        unassociated_line_id = 987654321
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['first-line-id']))
        self.confd.set_lines(MockLine(id='first-line-id', name='first-line-name', protocol='sip'),
                             MockLine(id=unassociated_line_id, name='unassociated-line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               line_id=unassociated_line_id,
                                               priority=priority,
                                               extension='my-extension',
                                               context='my-context',
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('line'),
                                                             contains_string('user')))

    def test_create_call_with_explicit_line(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        priority = 1
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['first-line-id', second_line_id]))
        self.confd.set_lines(MockLine(id='first-line-id', name='first-line-name', protocol='sip'),
                             MockLine(id=second_line_id, name='second-line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', priority)

        self.ctid_ng.originate(source=user_uuid,
                               line_id=second_line_id,
                               priority=priority,
                               extension='my-extension',
                               context='my-context')

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', str(priority)],
                               ['extension', 'my-extension'],
                               ['context', 'my-context'],
                               ['endpoint', 'sip/second-line-name'])}))))

    def test_create_call_from_mobile(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        mobile_context, mobile_extension, mobile_priority = 'my-line-context', 'my-mobile', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.amid.set_valid_exten(mobile_context, mobile_extension, mobile_priority)
        self.confd.set_users(MockUser(uuid='user-uuid', mobile=mobile_extension, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context=mobile_context))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        self.ctid_ng.originate(source=user_uuid,
                               from_mobile=True,
                               priority=priority,
                               extension=extension,
                               context=context)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', '1'],
                               ['extension', 's'],
                               ['context', 'wazo-originate-mobile-leg2'],
                               ['endpoint', 'local/s@wazo-originate-mobile-leg1/n']),
            'json': has_entry('variables', has_entries({'WAZO_ORIGINATE_DESTINATION_CONTEXT': context,
                                                        'WAZO_ORIGINATE_DESTINATION_EXTENSION': extension,
                                                        'WAZO_ORIGINATE_DESTINATION_PRIORITY': str(priority),
                                                        'WAZO_ORIGINATE_MOBILE_CONTEXT': mobile_context,
                                                        'WAZO_ORIGINATE_MOBILE_EXTENSION': mobile_extension,
                                                        'WAZO_ORIGINATE_MOBILE_PRIORITY': '1'}))
        }))))

    def test_create_call_from_mobile_with_no_line(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(MockUser(uuid='user-uuid', mobile='my-mobile'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               from_mobile=True,
                                               priority=priority,
                                               extension=extension,
                                               context=context,
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('line'),
                                                             contains_string('user')))

    def test_create_call_from_mobile_with_no_mobile(self):
        user_uuid = 'user-uuid'
        priority = 1
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-line-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               from_mobile=True,
                                               priority=priority,
                                               extension=extension,
                                               context=context,
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('mobile'),
                                                             contains_string('user')))

    def test_create_call_from_mobile_with_invalid_mobile(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten(context, extension, priority)
        self.confd.set_users(MockUser(uuid='user-uuid', mobile='invalid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-line-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               from_mobile=True,
                                               priority=priority,
                                               extension=extension,
                                               context=context,
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('mobile'),
                                                             contains_string('invalid'),
                                                             contains_string('user')))

    def test_create_call_from_mobile_to_wrong_extension(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        self.amid.set_valid_exten('my-line-context', 'my-mobile', priority)
        self.confd.set_users(MockUser(uuid='user-uuid', mobile='my-mobile', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-line-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        result = self.ctid_ng.post_call_result(source=user_uuid,
                                               from_mobile=True,
                                               priority=priority,
                                               extension=extension,
                                               context=context,
                                               token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('exten')))

    def test_create_call_from_mobile_overrides_line_id(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        mobile_context, mobile_extension, mobile_priority = 'my-line-context', 'my-mobile', 1
        second_line_id = 12345
        self.amid.set_valid_exten(context, extension, priority)
        self.amid.set_valid_exten(mobile_context, mobile_extension, mobile_priority)
        self.confd.set_users(MockUser(uuid='user-uuid', mobile=mobile_extension, line_ids=['first-line-id', second_line_id]))
        self.confd.set_lines(MockLine(id='first-line-id', name='first-line-name', context=mobile_context, protocol='sip',),
                             MockLine(id=second_line_id, name='second-line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        self.ctid_ng.originate(source=user_uuid,
                               from_mobile=True,
                               line_id=second_line_id,
                               priority=priority,
                               extension=extension,
                               context=context)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', '1'],
                               ['extension', 's'],
                               ['context', 'wazo-originate-mobile-leg2'],
                               ['endpoint', 'local/s@wazo-originate-mobile-leg1/n']),
            'json': has_entry('variables', has_entries({'WAZO_ORIGINATE_DESTINATION_CONTEXT': context,
                                                        'WAZO_ORIGINATE_DESTINATION_EXTENSION': extension,
                                                        'WAZO_ORIGINATE_DESTINATION_PRIORITY': str(priority),
                                                        'WAZO_ORIGINATE_MOBILE_CONTEXT': mobile_context,
                                                        'WAZO_ORIGINATE_MOBILE_EXTENSION': mobile_extension,
                                                        'WAZO_ORIGINATE_MOBILE_PRIORITY': '1'}))
        }))))


class TestUserCreateCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestUserCreateCall, self).setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_given_no_confd_when_create_then_503(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))

        body = {'extension': 'my-extension'}

        with self.confd_stopped():
            result = self.ctid_ng.post_user_me_call_result(body, token)

        assert_that(result.status_code, equal_to(503))

    def test_given_invalid_input_when_create_then_error_400(self):
        for invalid_body in self.invalid_call_requests():
            response = self.ctid_ng.post_user_me_call_result(invalid_body, VALID_TOKEN)

            assert_that(response.status_code, equal_to(400))
            assert_that(response.json(), has_entries({'message': contains_string('invalid'),
                                                      'error_id': equal_to('invalid-data')}))

    def invalid_call_requests(self):
        valid_call_request = {
            'extension': '1234',
            'variables': {'key': 'value'}
        }

        for key in ('extension', 'variables'):
            body = dict(valid_call_request)
            body[key] = None
            yield body
            body[key] = 1234
            yield body
            body[key] = True
            yield body
            body[key] = ''
            yield body

        body = dict(valid_call_request)
        body.pop('extension')
        yield body

        body = dict(valid_call_request)
        body['variables'] = 'abcd'
        yield body

    def test_create_call_with_correct_values(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension')

        result = self.ctid_ng.originate_me(extension='my-extension', token=token)

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_when_create_call_then_ari_arguments_are_correct(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel('new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension')

        self.ctid_ng.originate_me(extension='my-extension',
                                  variables={'MY_VARIABLE': 'my-value',
                                             'SECOND_VARIABLE': 'my-second-value',
                                             'CONNECTEDLINE(name)': 'my-connected-line',
                                             'XIVO_FIX_CALLERID': '1'},
                                  token=token)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', '1'],
                               ['extension', 'my-extension'],
                               ['context', 'my-context'],
                               ['endpoint', 'sip/line-name']),
            'json': has_entries({'variables': has_entries({'MY_VARIABLE': 'my-value',
                                                           'SECOND_VARIABLE': 'my-second-value',
                                                           'CONNECTEDLINE(name)': 'my-connected-line',
                                                           'CONNECTEDLINE(num)': 'my-extension',
                                                           'CALLERID(name)': 'my-extension',
                                                           'CALLERID(num)': 'my-extension',
                                                           'XIVO_FIX_CALLERID': '1'})}),
        }))))

    def test_when_create_call_with_no_variables_then_default_variables_are_set(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension')

        self.ctid_ng.originate_me(extension='my-extension', token=token)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'json': has_entries({'variables': {'CONNECTEDLINE(name)': 'my-extension',
                                               'CONNECTEDLINE(num)': 'my-extension',
                                               'CALLERID(name)': 'my-extension',
                                               'CALLERID(num)': 'my-extension',
                                               'XIVO_FIX_CALLERID': '1'}}),
        }))))

    def test_create_call_with_multiple_lines(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id', 'line-id2']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension')

        result = self.ctid_ng.originate_me(extension='my-extension', token=token)

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_create_call_with_no_lines(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid'))
        self.confd.set_user_lines({'user-uuid': []})
        self.amid.set_valid_exten('my-context', 'my-extension')

        body = {'extension': 'my-extension'}
        result = self.ctid_ng.post_user_me_call_result(body, token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('line'))

    def test_create_call_with_invalid_user(self):
        user_uuid = 'user-uuid-not-found'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.amid.set_valid_exten('my-context', 'my-extension')

        body = {'extension': 'my-extension'}
        result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_create_call_with_wrong_exten(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_no_valid_exten()

        body = {'extension': 'not-found'}
        result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('exten'))

    def test_create_call_with_no_content_type(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid=user_uuid, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension')

        with self.ctid_ng.send_no_content_type():
            body = {'extension': 'my-extension'}
            result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(201), result.json())

    def test_create_call_with_explicit_line(self):
        user_uuid = 'user-uuid'
        second_line_id = 12345
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['first-line-id', second_line_id]))
        self.confd.set_lines(MockLine(id='first-line-id', name='first-line-name', protocol='sip', context='first-context'),
                             MockLine(id=second_line_id, name='second-line-name', protocol='sip', context='second-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('second-context', 'my-extension')

        self.ctid_ng.originate_me('my-extension', line_id=second_line_id, token=token)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', '1'],
                               ['extension', 'my-extension'],
                               ['context', 'second-context'],
                               ['endpoint', 'sip/second-line-name'])}))))

    def test_create_call_from_mobile(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        mobile_context, mobile_extension, mobile_priority = 'my-context', 'my-mobile', 1
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', mobile=mobile_extension, line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context=mobile_context))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten(context, extension, priority)
        self.amid.set_valid_exten(mobile_context, mobile_extension, mobile_priority)

        self.ctid_ng.originate_me('my-extension', from_mobile=True, token=token)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', '1'],
                               ['extension', 's'],
                               ['context', 'wazo-originate-mobile-leg2'],
                               ['endpoint', 'local/s@wazo-originate-mobile-leg1/n']),
            'json': has_entry('variables', has_entries({'WAZO_ORIGINATE_DESTINATION_CONTEXT': context,
                                                        'WAZO_ORIGINATE_DESTINATION_EXTENSION': extension,
                                                        'WAZO_ORIGINATE_DESTINATION_PRIORITY': str(priority),
                                                        'WAZO_ORIGINATE_MOBILE_CONTEXT': mobile_context,
                                                        'WAZO_ORIGINATE_MOBILE_EXTENSION': mobile_extension,
                                                        'WAZO_ORIGINATE_MOBILE_PRIORITY': '1'}))
        }))))

    def test_create_call_from_mobile_with_no_line(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', mobile='my-mobile'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        body = {'extension': 'my-extension', 'from_mobile': True}
        result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('line'),
                                                             contains_string('user')))

    def test_create_call_from_mobile_with_no_mobile(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', 1)

        body = {'extension': 'my-extension', 'from_mobile': True}
        result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('mobile'),
                                                             contains_string('user')))

    def test_create_call_from_mobile_with_invalid_mobile(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', mobile='invalid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-context', 'my-extension', 1)

        body = {'extension': 'my-extension', 'from_mobile': True}
        result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('mobile'),
                                                             contains_string('invalid'),
                                                             contains_string('user')))

    def test_create_call_from_mobile_to_wrong_extension(self):
        user_uuid = 'user-uuid'
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', mobile='my-mobile', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip', context='my-line-context'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten('my-line-context', 'my-mobile', 1)

        body = {'extension': 'my-extension', 'from_mobile': True}
        result = self.ctid_ng.post_user_me_call_result(body, token=token)

        assert_that(result.status_code, equal_to(400), result.json())
        assert_that(result.json()['message'].lower(), all_of(contains_string('exten')))

    def test_create_call_from_mobile_overrides_line_id(self):
        user_uuid = 'user-uuid'
        context, extension, priority = 'my-context', 'my-extension', 1
        mobile_context, mobile_extension, mobile_priority = 'my-context', 'my-mobile', 1
        second_line_id = 12345
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid))
        self.confd.set_users(MockUser(uuid='user-uuid', mobile=mobile_extension, line_ids=['first-line-id', second_line_id]))
        self.confd.set_lines(MockLine(id='first-line-id', name='first-line-name', context=context, protocol='sip',),
                             MockLine(id=second_line_id, name='second-line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))
        self.amid.set_valid_exten(context, extension, priority)
        self.amid.set_valid_exten(mobile_context, mobile_extension, mobile_priority)

        self.ctid_ng.originate_me(extension, from_mobile=True, line_id=second_line_id, token=token)

        assert_that(self.ari.requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': has_items(['priority', '1'],
                               ['extension', 's'],
                               ['context', 'wazo-originate-mobile-leg2'],
                               ['endpoint', 'local/s@wazo-originate-mobile-leg1/n']),
            'json': has_entry('variables', has_entries({'WAZO_ORIGINATE_DESTINATION_CONTEXT': context,
                                                        'WAZO_ORIGINATE_DESTINATION_EXTENSION': extension,
                                                        'WAZO_ORIGINATE_DESTINATION_PRIORITY': str(priority),
                                                        'WAZO_ORIGINATE_MOBILE_CONTEXT': mobile_context,
                                                        'WAZO_ORIGINATE_MOBILE_EXTENSION': mobile_extension,
                                                        'WAZO_ORIGINATE_MOBILE_PRIORITY': '1'}))
        }))))


class TestFailingARI(IntegrationTest):

    asset = 'failing_ari'
    wait_strategy = CtidNgUpWaitStrategy()

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
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        result = self.ctid_ng.post_call_result(source='user-uuid',
                                               priority=SOME_PRIORITY,
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
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.ari.set_originates(MockChannel(id='new-call-id'))

        new_call = self.ctid_ng.connect_user('call-id', 'user-uuid')

        assert_that(new_call, has_entries({
            'call_id': 'new-call-id'
        }))
        assert_that(self.ari.requests(), has_entry('requests', has_items(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'query': contains_inanyorder(['app', 'callcontrol'], ['endpoint', 'sip/line-name'], ['appArgs', 'sw1,dialed_from,call-id'], ['originator', 'call-id']),
        }))))

    def test_given_no_confd_when_connect_user_then_503(self):
        with self.confd_stopped():
            result = self.ctid_ng.put_call_user_result(call_id='call-id',
                                                       user_uuid='user-uuid',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_user_when_connect_user_then_400(self):
        self.ari.set_channels(MockChannel(id='call-id'))

        result = self.ctid_ng.put_call_user_result('call-id', 'user-uuid', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_given_user_has_no_line_when_connect_user_then_400(self):
        self.ari.set_channels(MockChannel(id='call-id'))
        self.confd.set_users(MockUser(uuid='user-uuid'))

        result = self.ctid_ng.put_call_user_result('call-id', 'user-uuid', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json()['message'].lower(), contains_string('user'))

    def test_given_no_call_when_connect_user_then_404(self):
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='line-name', protocol='sip'))

        result = self.ctid_ng.put_call_user_result('call-id', 'user-uuid', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))
        assert_that(result.json()['message'].lower(), contains_string('call'))


class TestCallerID(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def test_when_create_call_and_answer1_then_connected_line_is_correct(self):
        self.confd.set_users(MockUser(uuid='user-uuid', line_ids=['line-id']))
        self.confd.set_lines(MockLine(id='line-id', name='originator', protocol='test'))
        originator_call = self.ctid_ng.originate('user-uuid',
                                                 priority='1',
                                                 extension='ring-connected-line',
                                                 context='local')
        originator_channel = self.ari.channels.get(channelId=originator_call['call_id'])
        recipient_caller_id_name = u'rêcîpîênt'
        recipient_caller_id_number = u'ring-connected-line'
        bus_events = self.bus.accumulator('calls.call.updated')

        self.chan_test.answer_channel(originator_channel.id)

        def originator_has_correct_connected_line(name, number):
            expected_peer_caller_id = {'name': name,
                                       'number': number}
            peer_caller_ids = [{'name': message['data']['peer_caller_id_name'],
                                'number': message['data']['peer_caller_id_number']}
                               for message in bus_events.accumulate()
                               if message['data']['call_id'] == originator_channel.id]

            return expected_peer_caller_id in peer_caller_ids

        until.true(originator_has_correct_connected_line, recipient_caller_id_name, recipient_caller_id_number, tries=3)
