# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class ChatsContexts:
    contexts = {}

    @classmethod
    def add(cls, key_part1, key_part2, **kwargs):
        key = cls._build_key(key_part1, key_part2)
        cls.contexts[key] = kwargs

    @classmethod
    def get(cls, key_part1, key_part2):
        key = cls._build_key(key_part1, key_part2)
        return cls.contexts.get(key)

    @staticmethod
    def _build_key(part1, part2):
        return '{}-{}'.format(part1, part2)
