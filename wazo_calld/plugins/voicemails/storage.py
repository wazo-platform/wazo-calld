# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import errno
import logging
import os.path

from operator import itemgetter

from xivo import caller_id

from .exceptions import NoSuchVoicemailFolder
from .exceptions import NoSuchVoicemailMessage
from .exceptions import VoicemailMessageStorageError

logger = logging.getLogger(__name__)


class VoicemailFolderType:
    new = 'new'
    old = 'old'
    urgent = 'urgent'
    other = 'other'


def new_filesystem_storage(base_path=b'/var/spool/asterisk/voicemail'):
    folders = _VoicemailFolders([
        _VoicemailFolder(1, b'INBOX', VoicemailFolderType.new, True),
        _VoicemailFolder(2, b'Old', VoicemailFolderType.old),
        _VoicemailFolder(3, b'Urgent', VoicemailFolderType.urgent, True),
        _VoicemailFolder(4, b'Work'),
        _VoicemailFolder(5, b'Family'),
        _VoicemailFolder(6, b'Friends'),
    ])
    return _VoicemailFilesystemStorage(base_path, folders)


def new_cache(voicemail_storage):
    return _VoicemailMessagesCache(voicemail_storage)


class _VoicemailFolder:

    def __init__(self, id_, path, type_=VoicemailFolderType.other, is_unread=False):
        self.id = id_
        self.path = path
        self.type = type_
        self.name = self.path.lower().decode('utf-8')
        self.is_unread = is_unread


class _VoicemailFolders:

    def __init__(self, folders):
        self._folders = folders

    def get_folder_by_id(self, folder_id):
        for folder in self._folders:
            if folder.id == folder_id:
                return folder
        raise NoSuchVoicemailFolder(folder_id=folder_id)

    def get_folder_by_type(self, folder_type):
        for folder in self._folders:
            if folder.type == folder_type:
                return folder
        raise NoSuchVoicemailFolder(folder_type=folder_type)

    def __iter__(self):
        return iter(self._folders)


class _VoicemailFilesystemStorage:

    def __init__(self, base_path, folders):
        self._base_path = base_path
        self._folders = folders

    def list_voicemails_number_and_context(self):
        for context in os.listdir(self._base_path):
            context_path = os.path.join(self._base_path, context)
            try:
                numbers = os.listdir(context_path)
            except OSError as e:
                logger.error('unexpected error while listing %s: %s', context_path, e)
            else:
                context = context.decode('utf-8')
                for number in numbers:
                    yield number.decode('utf-8'), context

    def get_voicemails_info(self):
        for context in os.listdir(self._base_path):
            context_path = os.path.join(self._base_path, context)
            try:
                numbers = os.listdir(context_path)
            except OSError as e:
                logger.error('unexpected error while listing %s: %s', context_path, e)
            else:
                for number in numbers:
                    vm_conf = _fake_vm_conf(number.decode('utf-8'), context.decode('utf-8'))
                    try:
                        yield self.get_voicemail_info(vm_conf)
                    except Exception as e:
                        logger.exception('unexpected error while getting voicemail info %s@%s: %s',
                                         number, context, e)

    def get_voicemail_info(self, vm_conf):
        vm_access = _VoicemailAccess(self._base_path, self._folders, vm_conf)
        vm_info = vm_access.info()
        for folder_access in vm_access.folders():
            folder_info = folder_access.info()
            for message_access in folder_access.messages():
                folder_info['messages'].append(message_access.info())
            self._sort_messages(folder_info['messages'])
            vm_info['folders'].append(folder_info)
        return vm_info

    def get_folder_info(self, vm_conf, folder_id):
        vm_access = _VoicemailAccess(self._base_path, self._folders, vm_conf)
        folder_access = vm_access.folder(folder_id)
        folder_info = folder_access.info()
        for message_access in folder_access.messages():
            folder_info['messages'].append(message_access.info())
        self._sort_messages(folder_info['messages'])
        return folder_info

    def get_folder_by_id(self, folder_id):
        return self._folders.get_folder_by_id(folder_id)

    def get_folder_by_type(self, folder_type):
        return self._folders.get_folder_by_type(folder_type)

    def get_message_info(self, vm_conf, message_id):
        vm_access = _VoicemailAccess(self._base_path, self._folders, vm_conf)
        message_access = vm_access.get_message(message_id)
        return message_access.info()

    def get_message_info_and_recording(self, vm_conf, message_id):
        vm_access = _VoicemailAccess(self._base_path, self._folders, vm_conf)
        message_access = vm_access.get_message(message_id)
        return message_access.info(), message_access.recording()

    def _sort_messages(self, messages):
        messages.sort(key=itemgetter('timestamp'), reverse=True)


class _VoicemailAccess:

    def __init__(self, base_path, folders, vm_conf):
        self.path = os.path.join(base_path,
                                 vm_conf['context'].encode('utf-8'),
                                 vm_conf['number'].encode('utf-8'))
        self._folders = folders
        self.vm_conf = vm_conf

    def folder(self, folder_id):
        return _FolderAccess(self, self._folders.get_folder_by_id(folder_id))

    def folders(self):
        for folder in self._folders:
            yield _FolderAccess(self, folder)

    def get_message(self, message_id):
        for folder_access in self.folders():
            for message_access in folder_access.messages():
                if message_access.id == message_id:
                    return message_access
        raise NoSuchVoicemailMessage(message_id)

    def info(self):
        return {
            'id': self.vm_conf['id'],
            'number': self.vm_conf['number'],
            'context': self.vm_conf['context'],
            'name': self.vm_conf['name'],
            'folders': [],
        }


class _FolderAccess:

    def __init__(self, vm_access, folder):
        self.vm_access = vm_access
        self.folder = folder
        self.path = os.path.join(vm_access.path, folder.path)

    def messages(self):
        try:
            names = os.listdir(self.path)
        except OSError as e:
            if e.errno == errno.ENOENT:
                # probably: no messages have been left in this folder
                return
            raise
        for name in names:
            if name.endswith(b'.txt'):
                yield _MessageAccess(self, name)

    def info(self):
        return {
            'id': self.folder.id,
            'name': self.folder.name,
            'type': self.folder.type,
            'messages': [],
        }


class _MessageInfoParser:

    def __init__(self):
        self._parse_table = [
            (b'callerid=', self._extract_value, self._parse_callerid),
            (b'msg_id=', self._extract_value, self._parse_msg_id),
            (b'origtime=', self._extract_value, self._parse_origtime),
            (b'duration=', self._extract_value, self._parse_duration),
        ]

    def parse(self, fobj):
        result = {}
        parsed = set()
        for line in fobj:
            for prefix, extract, parse in self._parse_table:
                if line.startswith(prefix):
                    parsed.add(prefix)
                    value = extract(line)
                    parse(value, result)
        # check that everything was parsed
        for prefix, _, _ in self._parse_table:
            if prefix not in parsed:
                raise Exception('no line starting with {}'.format(prefix))
        return result

    @staticmethod
    def _extract_value(line):
        return line.split(b'=', 1)[1].rstrip()

    @staticmethod
    def _parse_callerid(value, result):
        value = value.decode('utf-8')
        if value == 'Unknown':
            result['caller_id_name'] = None
            result['caller_id_num'] = None
        elif caller_id.is_complete_caller_id(value):
            result['caller_id_name'] = caller_id.extract_displayname(value)
            result['caller_id_num'] = caller_id.extract_number(value)
        else:
            result['caller_id_name'] = None
            result['caller_id_num'] = value

    @staticmethod
    def _parse_msg_id(value, result):
        result['id'] = value.decode('ascii')

    @staticmethod
    def _parse_origtime(value, result):
        result['timestamp'] = int(value)

    @staticmethod
    def _parse_duration(value, result):
        result['duration'] = int(value)


class _MessageAccess:

    _MESSAGE_INFO_PARSER = _MessageInfoParser()

    def __init__(self, folder_access, message_info_name):
        self.folder_access = folder_access
        self.name_prefix = os.path.splitext(message_info_name)[0]
        self.path_prefix = os.path.join(folder_access.path, self.name_prefix)
        self._read_message_info_file()

    def _read_message_info_file(self):
        path = self.path_prefix + b'.txt'
        try:
            with open(path, 'rb') as fobj:
                self.parse_result = self._MESSAGE_INFO_PARSER.parse(fobj)
            self.id = self.parse_result['id']
        except IOError as e:
            if e.errno == errno.ENOENT:
                # probably: the message has been deleted/moved
                logger.error('could not read voicemail message %s: no such file', path)
                raise VoicemailMessageStorageError()
            raise
        except Exception:
            logger.error('error while parsing voicemail message info %s', path, exc_info=True)
            raise VoicemailMessageStorageError()

    def info(self):
        info = dict(self.parse_result)
        info['folder'] = self.folder_access.folder
        info['vm_conf'] = self.folder_access.vm_access.vm_conf
        return info

    def recording(self):
        path = self.path_prefix + b'.wav'
        try:
            with open(path, 'rb') as fobj:
                return fobj.read()
        except IOError as e:
            if e.errno == errno.ENOENT:
                # probably: the message has been deleted/moved or the recording is not stored as a wav
                logger.error('could not read voicemail recording %s: no such file', path)
                raise VoicemailMessageStorageError()
            raise


class _VoicemailMessagesCache:

    _EMPTY_CACHE_ENTRY = {}

    def __init__(self, voicemail_storage, cache_cleanup_counter_max=1500):
        self._storage = voicemail_storage
        self._cache = {}
        self._cache_cleanup_counter = 0
        self._cache_cleanup_counter_max = cache_cleanup_counter_max

    def refresh_cache(self):
        self._cache = {}
        for vm_info in self._storage.get_voicemails_info():
            cache_entry = self._vm_info_to_cache_entry(vm_info)
            key = (vm_info['number'], vm_info['context'])
            self._cache[key] = cache_entry

    def get_diff(self, number, context):
        key = (number, context)
        vm_conf = _fake_vm_conf(number, context)
        old_cache_entry = self._cache.get(key, self._EMPTY_CACHE_ENTRY)
        new_vm_info = self._storage.get_voicemail_info(vm_conf)
        new_cache_entry = self._vm_info_to_cache_entry(new_vm_info)
        self._cache[key] = new_cache_entry
        self._maybe_clean_cache()
        return self._compute_diff(old_cache_entry, new_cache_entry)

    def _maybe_clean_cache(self):
        if self._cache_cleanup_counter == self._cache_cleanup_counter_max:
            self._cache_cleanup_counter = 0
            self._clean_cache()
        else:
            self._cache_cleanup_counter += 1

    def _clean_cache(self):
        logger.info('cleaning voicemail cache')
        cached_keys = set(self._cache)
        keys_to_purge = cached_keys.difference(self._storage.list_voicemails_number_and_context())
        for key in keys_to_purge:
            del self._cache[key]

    def _vm_info_to_cache_entry(self, vm_info):
        cache_entry = {}
        for folder_info in vm_info['folders']:
            for message_info in folder_info['messages']:
                cache_entry[message_info['id']] = message_info
        return cache_entry

    def _compute_diff(self, old_cache_entry, new_cache_entry):
        diff = _VoicemailMessagesDiff()
        for message_id, old_message_info in old_cache_entry.items():
            new_message_info = new_cache_entry.get(message_id)
            if new_message_info is None:
                diff.deleted_messages.append(old_message_info)
            elif old_message_info != new_message_info:
                diff.updated_messages.append(new_message_info)
        for message_id, new_message_info in new_cache_entry.items():
            if message_id not in old_cache_entry:
                diff.created_messages.append(new_message_info)
        return diff

    def __len__(self):
        return len(self._cache)


class _VoicemailMessagesDiff:

    def __init__(self):
        self.created_messages = []
        self.updated_messages = []
        self.deleted_messages = []

    def is_empty(self):
        return not self.created_messages and not self.updated_messages and not self.deleted_messages


def _fake_vm_conf(number, context):
    return {
        'id': 0,
        'name': 'fake-vm-conf',
        'number': number,
        'context': context,
    }
