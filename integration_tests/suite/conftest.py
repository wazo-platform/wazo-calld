# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest


@pytest.fixture(autouse=True, scope='function')
def mark_logs(request):
    test_name = f'{request.cls.__name__}.{request.function.__name__}'
    request.cls.mark_logs_test_start(test_name)
    yield
    request.cls.mark_logs_test_end(test_name)
