# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from tempfile import mkstemp


class FaxService:

    def __init__(self, amid, ari):
        self._amid = amid
        self._ari = ari

    def send_fax(self, tenant_uuid, content, fax_infos):
        fax_file_descriptor, fax_path = mkstemp(prefix='wazo-fax-', suffix='.tif')
        with os.fdopen(fax_file_descriptor, 'wb') as fax_file:
            fax_file.write(content)
        os.chmod(fax_path, 0o660)

        # send = self.amid.action('originate', {'Channel': 'Local/{exten}@{context}'.format(exten=extension, context),
        #                                       'CallerID': caller_id,
        #                                       'Variable': 'XIVO_USERID=%s' % fax_data.get('fax_user_id'),
        #                                       'Variable': 'XIVO_FAX_PATH=%s' % fax_path,
        #                                       'Context': 'txfax',
        #                                       'Exten': 's',
        #                                       'Async': 'true',
        #                                       'Priority': '1'})

        originate_variables = {
            'XIVO_USERID': fax_infos['user_id'],
            'XIVO_FAX_PATH': fax_path,
        }
        recipient_endpoint = 'Local/{exten}@{context}'.format(exten=fax_infos['extension'], context=fax_infos['context'])
        new_channel = self._ari.channels.originate(endpoint=recipient_endpoint,
                                                   context='txfax',
                                                   extension='s',
                                                   priority='1',
                                                   callerId=fax_infos['caller_id'],
                                                   variables={'variables': originate_variables})
        return {
            'call_id': new_channel.id,
        }
