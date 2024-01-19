# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import os.path
import subprocess

from tempfile import mkstemp

from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.confd import User
from wazo_calld.plugin_helpers.exceptions import InvalidExtension

from .exceptions import FaxFailure

logger = logging.getLogger(__name__)


class FaxesService:
    def __init__(self, amid, ari, confd, notifier):
        self._amid = amid
        self._ari = ari
        self._confd = confd
        self._notifier = notifier

    def send_fax(self, tenant_uuid, content, fax_infos, user_uuid=None):
        context = fax_infos['context']
        extension = fax_infos['extension']
        if not ami.extension_exists(self._amid, context, extension):
            raise InvalidExtension(context, extension)

        pdf_file_descriptor, pdf_path = mkstemp(prefix='wazo-fax-', suffix='.pdf')
        with os.fdopen(pdf_file_descriptor, 'wb') as pdf_file:
            pdf_file.write(content)
            pdf_file.close()

        tif_path = f'{pdf_path}.tif'
        command = ['/usr/bin/wazo-pdf2fax', '-o', tif_path, pdf_path]
        logger.debug('Running command: %s', command)
        try:
            subprocess.run(command, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.debug('wazo-pdf2fax output: %s', e.stdout)
            logger.debug('wazo-pdf2fax stderr: %s', e.stderr)
            logger.error(e)
            raise FaxFailure(message='Conversion from PDF to TIFF format failed')

        if not os.path.exists(tif_path):
            logger.error('wazo-pdf2fax: no output file "%s"', tif_path)
            raise FaxFailure(
                message='Conversion from PDF to TIFF format failed: output file not found'
            )

        wait_time_str = (
            '' if fax_infos['wait_time'] is None else str(fax_infos['wait_time'])
        )
        originate_variables = {
            'WAZO_FAX_DESTINATION_CONTEXT': fax_infos['context'],
            'WAZO_FAX_DESTINATION_EXTENSION': fax_infos['extension'],
            'WAZO_FAX_DESTINATION_IVR_EXTENSION': fax_infos['ivr_extension'] or '',
            'WAZO_FAX_DESTINATION_WAIT_TIME': wait_time_str,
            'WAZO_TENANT_UUID': tenant_uuid,
            'XIVO_FAX_PATH': tif_path,
            'WAZO_USERUUID': user_uuid or '',
        }
        recipient_endpoint = 'Local/{exten}@{context}'.format(
            exten=fax_infos['extension'], context=fax_infos['context']
        )
        new_channel = self._ari.channels.originate(
            endpoint=recipient_endpoint,
            context='txfax',
            extension='s',
            priority='1',
            callerId=fax_infos['caller_id'],
            variables={'variables': originate_variables},
        )
        fax = {
            'id': new_channel.id,
            'call_id': new_channel.id,
            'extension': fax_infos['extension'],
            'context': fax_infos['context'],
            'caller_id': fax_infos['caller_id'],
            'ivr_extension': fax_infos['ivr_extension'],
            'wait_time': fax_infos['wait_time'],
            'user_uuid': user_uuid,
            'tenant_uuid': tenant_uuid,
        }
        self._notifier.notify_fax_created(fax)
        return fax

    def send_fax_from_user(self, tenant_uuid, user_uuid, content, fax_infos):
        context = User(user_uuid, self._confd).main_line().context()

        fax_infos['context'] = context

        return self.send_fax(tenant_uuid, content, fax_infos, user_uuid=user_uuid)
