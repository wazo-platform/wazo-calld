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
import phonenumbers

from phonenumbers import carrier
from phonenumbers import geocoder
from phonenumbers import timezone

from flask.ext.restful import Resource


logger = logging.getLogger(__name__)


class LookupService(Resource):

    def lookup(self, phone_number):
        country_code = 'US'
        lang = 'en'
        number = phonenumbers.parse(phone_number, country_code)

        return {
            'country_code': geocoder.region_code_for_number(number),
            'country': geocoder.country_name_for_number(number, lang),
            'state_code': geocoder.description_for_number(number, lang),
            'phone_number': phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
            'national_format': phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL),
            'international_format': phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            'carrier': carrier.name_for_number(number, lang),
            'timezone': timezone.time_zones_for_number(number)
        }
