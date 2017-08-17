#!/usr/bin/python3

import sys
import struct


def from_ejabberd():
    input_length = sys.stdin.read(2).encode('utf-8')

    if len(input_length) is not 2:
        return None

    (size,) = struct.unpack('>h', input_length)
    return sys.stdin.read(size).split(':')


def to_ejabberd(bool):
    answer = 0
    if bool:
        answer = 1
    token = struct.pack('>hh', 2, answer).decode('utf-8')
    sys.stdout.write(token)
    sys.stdout.flush()


def auth(username, server, password):
    return False


def isuser(username, server):
    return True


def main():
    while True:
        data = from_ejabberd()
        success = False

        if data[0] == "auth":
            success = auth(data[1], data[2], data[3])
        elif data[0] == "isuser":
            success = isuser(data[1], data[2])
        to_ejabberd(success)


if __name__ == '__main__':
    main()
