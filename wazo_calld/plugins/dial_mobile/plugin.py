# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .stasis import DialMobileStasis
from .service import DialMobileService


class Plugin:

    def load(self, dependencies):
        ari = dependencies['ari']

        service = DialMobileService(ari)

        stasis = DialMobileStasis(ari, service)
        stasis.subscribe()
        stasis.add_ari_application()
