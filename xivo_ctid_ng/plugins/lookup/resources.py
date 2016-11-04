# -*- coding: utf-8 -*-
# Copyright (C) 2016 Proformatique INC
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

import logging

from flask.ext.restful import Resource

logger = logging.getLogger(__name__)


class Lookup(Resource):

    def __init__(self, lookup_service):
        self.lookup_service = lookup_service

    def get(self, phone_number):
        return self.lookup_service.lookup(phone_number), 200
