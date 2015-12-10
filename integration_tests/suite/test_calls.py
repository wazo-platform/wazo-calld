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

from .base import IntegrationTest
from .base import MockApplication
from .base import MockBridge
from .base import MockChannel
from .base import MockLine
from .base import MockUser
from .base import MockUserLine
from .base import VALID_TOKEN


class TestListCalls(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestListCalls, self).setUp()
        self.reset_ari()
        self.reset_confd()

    def test_given_no_calls_when_list_calls_then_empty_list(self):
        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains()))

    def test_given_some_calls_and_no_user_id_when_list_calls_then_list_calls_with_no_user_uuid(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'user_uuid': None}),
            has_entries({'call_id': 'second-id',
                         'user_uuid': None}))))

    def test_given_some_calls_with_user_id_when_list_calls_then_list_calls_with_user_uuid(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.set_ari_channel_variable({'first-id': {'XIVO_USERID': 'user1-id'},
                                       'second-id': {'XIVO_USERID': 'user2-id'}})
        self.set_confd_users(MockUser(id='user1-id', uuid='user1-uuid'),
                             MockUser(id='user2-id', uuid='user2-uuid'))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'user_uuid': 'user1-uuid'}),
            has_entries({'call_id': 'second-id',
                         'user_uuid': 'user2-uuid'}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_status(self):
        self.set_ari_channels(MockChannel(id='first-id', state='Up'),
                              MockChannel(id='second-id', state='Ringing'))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'status': 'Up'}),
            has_entries({'call_id': 'second-id',
                         'status': 'Ringing'}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_bridges(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.set_ari_bridges(MockBridge(id='first-bridge', channels=['first-id']),
                             MockBridge(id='second-bridge', channels=['second-id']))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'bridges': ['first-bridge']}),
            has_entries({'call_id': 'second-id',
                         'bridges': ['second-bridge']}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_talking_channels_and_users(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.set_ari_bridges(MockBridge(id='bridge-id', channels=['first-id', 'second-id']))
        self.set_ari_channel_variable({'first-id': {'XIVO_USERID': 'user1-id'},
                                       'second-id': {'XIVO_USERID': 'user2-id'}})
        self.set_confd_users(MockUser(id='user1-id', uuid='user1-uuid'),
                             MockUser(id='user2-id', uuid='user2-uuid'))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'talking_to': {'second-id': 'user2-uuid'}}),
            has_entries({'call_id': 'second-id',
                         'talking_to': {'first-id': 'user1-uuid'}}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_creation_time(self):
        self.set_ari_channels(MockChannel(id='first-id', creation_time='first-time'),
                              MockChannel(id='second-id', creation_time='second-time'))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'creation_time': 'first-time'}),
            has_entries({'call_id': 'second-id',
                         'creation_time': 'second-time'}))))

    def test_given_some_calls_when_list_calls_then_list_calls_with_caller_id(self):
        self.set_ari_channels(MockChannel(id='first-id', caller_id_name='Weber', caller_id_number='4185556666'),
                              MockChannel(id='second-id', caller_id_name='Denis', caller_id_number='4185557777'))

        calls = self.list_calls()

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id',
                         'caller_id_number': '4185556666',
                         'caller_id_name': 'Weber'}),
            has_entries({'call_id': 'second-id',
                         'caller_id_number': '4185557777',
                         'caller_id_name': 'Denis'}))))

    def test_given_some_calls_when_list_calls_by_application_then_list_of_calls_is_filtered(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'),
                              MockChannel(id='third-id'))
        self.set_ari_applications(MockApplication(name='my-app', channels=['first-id', 'third-id']))

        calls = self.list_calls(application='my-app')

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}),
            has_entries({'call_id': 'third-id'}))))

    def test_given_some_calls_and_no_applications_when_list_calls_by_application_then_no_calls(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))

        calls = self.list_calls(application='my-app', token=VALID_TOKEN)

        assert_that(calls, has_entry('items', empty()))

    def test_given_some_calls_when_list_calls_by_application_instance_then_list_of_calls_is_filtered(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'),
                              MockChannel(id='third-id'),
                              MockChannel(id='fourth-id'))
        self.set_ari_applications(MockApplication(name='my-app', channels=['first-id', 'second-id', 'third-id']))
        self.set_ari_channel_variable({'first-id': {'XIVO_STASIS_ARGS': 'appX'},
                                       'second-id': {'XIVO_STASIS_ARGS': 'appY'},
                                       'third-id': {'XIVO_STASIS_ARGS': 'appX'}})

        calls = self.list_calls(application='my-app', application_instance='appX')

        assert_that(calls, has_entry('items', contains_inanyorder(
            has_entries({'call_id': 'first-id'}),
            has_entries({'call_id': 'third-id'}))))


class TestGetCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestGetCall, self).setUp()
        self.reset_ari()
        self.reset_confd()

    def test_given_no_calls_when_get_call_then_404(self):
        call_id = 'not-found'

        result = self.get_call_result(call_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_one_call_when_get_call_then_get_call(self):
        self.set_ari_channels(MockChannel(id='first-id', state='Up', creation_time='first-time', caller_id_name='Weber', caller_id_number='4185559999'),
                              MockChannel(id='second-id'))
        self.set_ari_bridges(MockBridge(id='bridge-id', channels=['first-id', 'second-id']))
        self.set_ari_channel_variable({'first-id': {'XIVO_USERID': 'user1-id'},
                                       'second-id': {'XIVO_USERID': 'user2-id'}})
        self.set_confd_users(MockUser(id='user1-id', uuid='user1-uuid'),
                             MockUser(id='user2-id', uuid='user2-uuid'))

        call = self.get_call('first-id')

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
        self.reset_ari()
        self.reset_confd()

    def test_given_no_calls_when_delete_call_then_404(self):
        call_id = 'not-found'

        result = self.delete_call_result(call_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_given_one_call_when_delete_call_then_call_hungup(self):
        call_id = 'call-id'
        self.set_ari_channels(MockChannel(id=call_id, state='Up'))

        self.hangup_call(call_id)

        assert_that(self.ari_requests(), has_entry('requests', has_item(has_entries({
            'method': 'DELETE',
            'path': '/ari/channels/call-id',
        }))))


class TestCreateCall(IntegrationTest):

    asset = 'basic_rest'

    def setUp(self):
        super(TestCreateCall, self).setUp()
        self.reset_ari()
        self.reset_confd()

    def test_create_call_with_correct_values(self):
        user_uuid = 'user-uuid'
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id')]})
        self.set_ari_originates(MockChannel(id='new-call-id'))

        result = self.originate(source=user_uuid,
                                priority='my-priority',
                                extension='my-extension',
                                context='my-context')

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari_requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_when_create_call_then_ari_arguments_are_correct(self):
        user_uuid = 'user-uuid'
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id')]})
        self.set_ari_originates(MockChannel(id='new-call-id'))

        self.originate(source=user_uuid,
                       priority='my-priority',
                       extension='my-extension',
                       context='my-context',
                       variables={'MY_VARIABLE': 'my-value',
                                  'SECOND_VARIABLE': 'my-second-value'})

        assert_that(self.ari_requests(), has_entry('requests', has_item(has_entries({
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
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id')]})
        self.set_ari_originates(MockChannel(id='new-call-id'))

        self.originate(source=user_uuid,
                       priority='my-priority',
                       extension='my-extension',
                       context='my-context')

        assert_that(self.ari_requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
            'json': has_entries({'variables': {}}),
        }))))

    def test_create_call_with_multiple_lines(self):
        user_uuid = 'user-uuid'
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id2', main_line=False),
                                               MockUserLine('user-id', 'line-id', main_line=True)]})
        self.set_ari_originates(MockChannel(id='new-call-id'))

        result = self.originate(source=user_uuid,
                                priority='my-priority',
                                extension='my-extension',
                                context='my-context')

        assert_that(result, has_entry('call_id', 'new-call-id'))
        assert_that(self.ari_requests(), has_entry('requests', has_item(has_entries({
            'method': 'POST',
            'path': '/ari/channels',
        }))))

    def test_create_call_with_no_lines(self):
        user_uuid = 'user-uuid'
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_user_lines({'user-id': []})

        result = self.post_call_result(source=user_uuid,
                                       priority='my-priority',
                                       extension='my-extension',
                                       context='my-context',
                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('line')))

    def test_create_call_with_invalid_user(self):
        user_uuid = 'user-uuid-not-found'

        result = self.post_call_result(source=user_uuid,
                                       priority='my-priority',
                                       extension='my-extension',
                                       context='my-context', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('user')))

    def test_create_call_with_missing_source(self):
        body = {'destination': {'priority': '1',
                                'extension': 'myexten',
                                'context': 'mycontext'}}
        result = self.post_call_raw(body, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))
        assert_that(result.json(), has_entry('message', contains_string('source')))


class TestNoConfd(IntegrationTest):

    asset = 'no_confd'

    def setUp(self):
        super(TestNoConfd, self).setUp()
        self.reset_ari()

    def test_given_some_calls_and_no_confd_when_list_calls_then_503(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.set_ari_channel_variable({'first-id': {'XIVO_USERID': 'user1-id'},
                                       'second-id': {'XIVO_USERID': 'user2-id'}})

        result = self.get_calls_result(token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_some_calls_and_no_confd_when_get_call_then_503(self):
        self.set_ari_channels(MockChannel(id='first-id'),
                              MockChannel(id='second-id'))
        self.set_ari_channel_variable({'first-id': {'XIVO_USERID': 'user1-id'},
                                       'second-id': {'XIVO_USERID': 'user2-id'}})

        result = self.get_call_result('first-id', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_confd_when_originate_then_503(self):
        result = self.post_call_result(source='user-uuid',
                                       priority=None,
                                       extension=None,
                                       context=None,
                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))


class _BaseNoARI(IntegrationTest):

    def setUp(self):
        super(_BaseNoARI, self).setUp()
        self.reset_confd()

    def test_given_no_ari_when_list_calls_then_503(self):
        result = self.get_calls_result(token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_ari_when_get_call_then_503(self):
        result = self.get_call_result('first-id', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_ari_when_originate_then_503(self):
        self.set_confd_users(MockUser(id='user-id', uuid='user-uuid'))
        self.set_confd_lines(MockLine(id='line-id', name='line-name', protocol='sip'))
        self.set_confd_user_lines({'user-id': [MockUserLine('user-id', 'line-id')]})
        result = self.post_call_result(source='user-uuid',
                                       priority='priority',
                                       extension='extension',
                                       context='context',
                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_given_no_ari_when_delete_call_then_503(self):
        result = self.delete_call_result('call-id', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))


class TestNoARI(_BaseNoARI):

    asset = 'no_ari'


class TestFailingARI(_BaseNoARI):

    asset = 'failing_ari'
