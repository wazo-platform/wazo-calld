# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    calling,
    contains_inanyorder,
    equal_to,
    is_,
    none,
)
from mock import Mock
from unittest import TestCase
from xivo_test_helpers.hamcrest.raises import raises
from xivo_test_helpers.hamcrest.has_callable import has_callable

from ..relocate import (
    Relocate,
    RelocateCollection,
    RelocateRole,
)


class TestRelocate(TestCase):

    def setUp(self):
        self.factory = Mock()

    def test_role(self):
        relocate = Relocate(self.factory)
        relocate.relocated_channel = 'relocated'
        relocate.initiator_channel = 'initiator'
        relocate.recipient_channel = 'recipient'

        assert_that(relocate.role('relocated'), equal_to(RelocateRole.relocated))
        assert_that(relocate.role('initiator'), equal_to(RelocateRole.initiator))
        assert_that(relocate.role('recipient'), equal_to(RelocateRole.recipient))
        assert_that(calling(relocate.role).with_args('unknown'),
                    raises(KeyError).matching(has_callable('__str__', equal_to("'unknown'"))))


class TestRelocateCollection(TestCase):

    def setUp(self):
        self.factory = Mock()

    def test_add_get_remove(self):
        collection = RelocateCollection()
        relocate = Relocate(self.factory)

        assert_that(calling(collection.get).with_args(relocate.uuid),
                    raises(KeyError).matching(has_callable('__str__', "'{}'".format(relocate.uuid))))
        collection.add(relocate)
        assert_that(collection.get(relocate.uuid),
                    is_(relocate))
        collection.remove(relocate)
        assert_that(calling(collection.get).with_args(relocate.uuid),
                    raises(KeyError).matching(has_callable('__str__', "'{}'".format(relocate.uuid))))

    def test_given_relocate_when_relocate_ends_then_relocate_removed(self):
        collection = RelocateCollection()
        relocate = Relocate(self.factory)

        collection.add(relocate)
        assert_that(collection.get(relocate.uuid),
                    is_(relocate))

        relocate.events.publish('ended', relocate)
        assert_that(calling(collection.get).with_args(relocate.uuid),
                    raises(KeyError).matching(has_callable('__str__', "'{}'".format(relocate.uuid))))

    def test_given_no_relocates_when_get_by_channel_then_error(self):
        collection = RelocateCollection()

        assert_that(calling(collection.get_by_channel).with_args('unknown'),
                    raises(KeyError).matching(has_callable('__str__', "'unknown'")))

    def test_given_another_relocate_when_get_by_channel_then_error(self):
        collection = RelocateCollection()
        relocate = Relocate(self.factory)
        collection.add(relocate)

        assert_that(calling(collection.get_by_channel).with_args('unknown'),
                    raises(KeyError).matching(has_callable('__str__', "'unknown'")))

    def test_given_relocate_when_get_by_channel_then_return_relocate(self):
        collection = RelocateCollection()
        relocate = Relocate(self.factory)
        relocate.relocated_channel = 'relocated'
        relocate.initiator_channel = 'initiator'
        relocate.recipient_channel = 'recipient'
        collection.add(relocate)

        assert_that(collection.get_by_channel('relocated'), is_(relocate))
        assert_that(collection.get_by_channel('initiator'), is_(relocate))
        assert_that(collection.get_by_channel('recipient'), is_(relocate))

    def test_given_no_relocates_when_find_by_channel_then_none(self):
        collection = RelocateCollection()

        assert_that(collection.find_by_channel('unknown'), none())

    def test_given_another_relocate_when_find_by_channel_then_none(self):
        collection = RelocateCollection()
        relocate = Relocate(self.factory)
        collection.add(relocate)

        assert_that(collection.find_by_channel('unknown'), none())

    def test_given_relocate_when_find_by_channel_then_return_relocate(self):
        collection = RelocateCollection()
        relocate = Relocate(self.factory)
        relocate.relocated_channel = 'relocated'
        relocate.initiator_channel = 'initiator'
        relocate.recipient_channel = 'recipient'
        collection.add(relocate)

        assert_that(collection.find_by_channel('relocated'), is_(relocate))
        assert_that(collection.find_by_channel('initiator'), is_(relocate))
        assert_that(collection.find_by_channel('recipient'), is_(relocate))

    def test_list(self):
        collection = RelocateCollection()
        my_relocate = Relocate(self.factory)
        my_relocate.initiator = 'me'
        collection.add(my_relocate)
        your_relocate = Relocate(self.factory)
        your_relocate.initiator = 'you'
        collection.add(your_relocate)

        assert_that(collection.list(), contains_inanyorder(my_relocate, your_relocate))
