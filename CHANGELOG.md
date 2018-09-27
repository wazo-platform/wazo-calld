Changelog
=========

18.11
-----

* New API to start and stop music on hold on a call in an application

  * `PUT /applications/{application_uuid}/calls/{call_id}/moh/{moh_uuid}/start`
  * `PUT /applications/{application_uuid}/calls/{call_id}/moh/stop`

* New API to place a call on hold and resume it

  * `PUT /applications/{application_uuid}/calls/{call_id}/hold/start`
  * `PUT /applications/{application_uuid}/calls/{call_id}/hold/stop`


18.10
-----

* A new API to create custom applications has been added

  * `GET /applications/{application_uuid}`
  * `GET /applications/{application_uuid}/calls`
  * `POST /applications/{application_uuid}/calls`
  * `DELETE /applications/{application_uuid}/calls/{call_id}`
  * `POST /applications/{application_uuid}/calls/{call_id}/playbacks`
  * `GET /applications/{application_uuid}/nodes`
  * `POST /applications/{application_uuid}/nodes`
  * `GET /applications/{application_uuid}/nodes/{node_uuid}`
  * `DELETE /applications/{application_uuid}/nodes/{node_uuid}`
  * `POST /applications/{application_uuid}/nodes/{node_uuid}/calls`
  * `PUT /applications/{application_uuid}/nodes/{node_uuid}/calls/{call_id}`
  * `DELETE /applications/{application_uuid}/nodes/{node_uuid}/calls/{call_id}`
  * `DELETE /applications/{application_uuid}/playbacks/{playback_uuid}`


17.17
------

* New API for relocating calls:

  * `PUT /users/me/relocates/{relocate_uuid}/cancel`

* New field for calls:

  * `dialed_extension`


17.15
-----

* New APIs for relocating calls:

  * `GET,POST /users/me/relocates`
  * `GET /users/me/relocates/{relocate_uuid}`
  * `PUT /users/me/relocates/{relocate_uuid}/complete`


17.12
-----

* A new API for getting chat history:

  * GET `/1.0/users/me/chats`


17.05
-----

* New attribute `is_caller` for Call objects in routes:

  * `GET,POST /calls`
  * `GET /calls/{call_id}`
  * `GET,POST /users/me/calls`

17.03
-----

* New routes for switchboard operations. This is not (yet) related to the current switchboard
  implementation.

  * `GET /1.0/switchboards/{switchboard_uuid}/calls/held`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}/answer`

17.02
-----

* A new API for switchboard operations. This is not (yet) related to the current switchboard
  implementation.

  * `GET /1.0/switchboards/{switchboard_uuid}/calls/queued`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/queued/{call_id}/answer`

17.01
-----

* A new parameter for call creation (`POST /calls` and `POST /users/me/calls`)

  * `from_mobile`

16.16
-----

* A new API for managing voicemails messages:

    * GET `/1.0/voicemails/{voicemail_id}`
    * GET `/1.0/voicemails/{voicemail_id}/folders/{folder_id}`
    * DELETE `/1.0/voicemails/{voicemail_id}/messages/{message_id}`
    * GET `/1.0/voicemails/{voicemail_id}/messages/{message_id}`
    * PUT `/1.0/voicemails/{voicemail_id}/messages/{message_id}`
    * POST `/1.0/voicemails/{voicemail_id}/messages/{message_id}/recording`
    * GET `/1.0/users/me/voicemails`
    * GET `/1.0/users/me/voicemails/folders/{folder_id}`
    * DELETE `/1.0/users/me/voicemails/messages/{message_id}`
    * GET `/1.0/users/me/voicemails/messages/{message_id}`
    * PUT `/1.0/users/me/voicemails/messages/{message_id}`
    * POST `/1.0/users/me/voicemails/messages/{message_id}/recording`

* A new `timeout` parameter has been added to the following URL:

    * POST `/1.0/transfers`
    * POST `/1.0/users/me/transfers`

* A new `line_id` parameter has been added to the following URL:

    * POST `/1.0/calls`
    * POST `/1.0/users/me/calls`


16.11
-----

* A new API for getting the status of lines:

    * GET `/1.0/lines/{id}/presences`


16.10
-----

* A new API for checking the status of the daemon:

    * GET `/1.0/status`


16.09
-----

* A new API for updating user presences:

    * GET `/1.0/users/{uuid}/presences`
    * PUT `/1.0/users/{uuid}/presences`
    * GET `/1.0/users/me/presences`
    * PUT `/1.0/users/me/presences`

* New APIs for listing and hanging up calls of a user:

    * GET `/1.0/users/me/calls`
    * DELETE `/1.0/users/me/calls/{id}`

* New APIs for listing, cancelling and completing transfers of a user:

    * GET `/1.0/users/me/transfers`
    * DELETE `/1.0/users/me/transfers/{transfer_id}`
    * PUT `/1.0/users/me/transfers/{transfer_id}/complete`

* POST `/1.0/users/me/transfers` may now return 403 status code.
* Originates (POST `/*/calls`) now return 400 if an invalid extension is given.


16.08
-----

* A new API for making calls from the authenticated user:

    * POST `/1.0/users/me/calls`

* A new API for sending chat messages:

    * POST `/1.0/chats`
    * POST `/1.0/users/me/chats`

* A new parameter for transfer creation (POST `/1.0/transfers`):

    * `variables`

* A new API for making transfers from the authenticated user:

    * POST `/1.0/users/me/transfers`
