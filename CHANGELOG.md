# Changelog

## 25.02

* The following endpoints can now return a `403` when call recording is
  not enabled on the user, the queue or the group

  * `PUT /1.0/users/me/calls/<call_id>/record/start`
  * `PUT /1.0/users/me/calls/<call_id>/record/stop`
  * `PUT /1.0/calls/<call_id>/record/start`
  * `PUT /1.0/calls/<call_id>/record/stop`

* New API to resume and pause call recordings:
  * `PUT /1.0/users/me/calls/<call_id>/record/pause`
  * `PUT /1.0/users/me/calls/<call_id>/record/resume`
  * `PUT /1.0/calls/<call_id>/record/pause`
  * `PUT /1.0/calls/<call_id>/record/resume`

## 24.16

* The following endpoints are not marking a voicemail message as read anymore when accessed:
  * `GET /1.0/voicemails/<voicemail_id>/messages/<message_id>/recording`
  * `GET /1.0/users/me/voicemails/<voicemail_id>/messages/<message_id>/recording`
  If you want to mark a message as read, use the
  `PUT /1.0/voicemails/<voicemail_id>/messages/<message_id>` or
  `PUT /1.0/users/me/voicemails/messages/<message_id>` API to change the `folder_id` of the
  message to the `Old` folder (id 2).

## 24.13

* The following endpoints now enforce tenant isolation:

  * `GET /1.0/voicemails/<voicemail_id>`
  * `GET /1.0/voicemails/<voicemail_id>/folders/<folder_id>`
  * `GET /1.0/voicemails/<voicemail_id>/greetings/<greeting_id>`
  * `HEAD /1.0/voicemails/<voicemail_id>/greetings/<greeting_id>`
  * `POST /1.0/voicemails/<voicemail_id>/greetings/<greeting_id>`
  * `PUT /1.0/voicemails/<voicemail_id>/greetings/<greeting_id>`
  * `DELETE /1.0/voicemails/<voicemail_id>/greetings/<greeting_id>`
  * `POST /1.0/voicemails/<voicemail_id>/greetings/<greeting_id>/copy`
  * `GET /1.0/voicemails/<voicemail_id>/messages/<message_id>`
  * `PUT /1.0/voicemails/<voicemail_id>/messages/<message_id>`
  * `DELETE /1.0/voicemails/<voicemail_id>/messages/<message_id>`
  * `GET /1.0/voicemails/<voicemail_id>/messages/<message_id>/recording`

## 24.11

* The following endpoints are now performing additional validation before starting a call, which introduces a different behavior for existing error conditions:
  * `POST /1.0/calls`
  * `POST /1.0/users/me/calls`
  If the requested source line is of type SIP, and is not registered nor available, the API will respond with a 400 status and error id `call-origin-unavailable`

* The following endpoints now enforce tenant isolation:

  * `POST /1.0/calls`
  * `DELETE /1.0/calls/<call-id>`
  * `PUT /1.0/calls/<call_id>/user/<user_uuid>`
  * `PUT /1.0/calls/{call_id}/answer`
  * `PUT /1.0/calls/{call_id}/dtmf`
  * `PUT /1.0/calls/{call_id}/hold/start`
  * `PUT /1.0/calls/{call_id}/hold/stop`
  * `PUT /1.0/calls/{call_id}/record/start`
  * `PUT /1.0/calls/{call_id}/record/stop`
  * `PUT /1.0/calls/{call_id}/mute/start`
  * `PUT /1.0/calls/{call_id}/mute/stop`

  In order to make an action in another tenant, you need to specify the `Wazo-Tenant` HTTP header.

## 24.10

* The following endpoints now have Wazo-Tenant header to support multi-tenant

  * `GET /1.0/calls`
  * `GET /1.0/calls/<call-id>`

* The following endpoints have a new query parameter `recurse`:

  * `GET /1.0/calls`

## 24.08

* The `conversation_id` attribute has been added to the `application_call` object

* New API to list parkings and parked calls

  * GET `/parking_lots`

* The following attributes have been added to the `parking_lot` object:

  * `id`
  * `name`

* The following attributes have been added to the `parked_call` object:

  * `conversation_id`
  * `caller_id_name`
  * `caller_id_num`
  * `parker_caller_id_name`
  * `parker_caller_id_num`

## 24.05

* New API to manage a call parking

  * GET `/parking_lots/<parking-id>`
  * PUT `/calls/<call-id>/park`
  * PUT `/users/me/calls/<call-id>/park`

* New attribute for `calls` objects (API and events):

  * `parked`

## 24.02

* The `timeout` field has been added to the following resources:

  * PUT `/calls/<call-id>/user/<user-uuid>`

## 23.01

* The following bus configuration keys have been changed:

  * key `exchange_name` now defaults to `wazo-headers`
  * key `exchange_type` was removed

## 22.15

* The `direction` field has been added to the following resources:

  * GET `/calls`
  * GET `/calls/<call-id>`
  * GET `/users/me/calls`

* The `direction` field has been added to the following events:

  * `call_created`
  * `call_updated`
  * `call_answered`
  * `call_ended`

## 22.06

* New API to kick participants out of a meeting:

* `DELETE /meetings/{meeting_uuid}/participants/{participant_id}`
* `DELETE /users/me/meetings/{meeting_uuid}/participants/{participant_id}`

## 22.04

* The `answer_time` field has been added to the following resources:

  * GET `/calls`
  * GET `/calls/<call-id>`
  * GET `/users/me/calls`

* The `hangup_time` field has been added to the following resources:

  * GET `/calls`
  * GET `/calls/<call-id>`
  * GET `/users/me/calls`

* The `answer_time` and `hangup_time` fields have been added to the following events:

  * `call_created`
  * `call_updated`
  * `call_answered`
  * `call_ended`

* The `ivr_extension` and `wait_time` fields have been added to the following resources:

  * POST `/faxes`
  * POST `/users/me/faxes`

* The `is_video` field has been added to the following resources:

  * GET `/calls`
  * GET `/calls/<call-id>`
  * GET `/users/me/calls`

* New attribute for `Transfer` objects:

  * `initiator_tenant_uuid`

## 22.03

* New API to get the status of a meeting:

* `GET /guests/me/meetings/{meeting_uuid}/status`

## 21.13

* New API to get participants in a meeting:

* `GET /meetings/{meeting_uuid}/participants`
* `GET /users/me/meetings/{meeting_uuid}/participants`

## 21.10

* The event `call_ended` now send `reason_code` to know why a call was ended`.
* The event `call_ended` now contains the `is_caller` field of the call.

## 21.09

* New endpoint to get and update configuration of `wazo-calld`:

  * `GET /config`
  * `PATCH /config`
    * Only the `debug` attribute may be modified.

## 21.08

* The event `call_missed` now contains a `conversation_id` whenever a call is missed or refused.

## 21.05

* New attribute for `calls` objects (API and events):

  * `conversation_id`

## 21.02

* The following endpoints now filter out whitespace in the requested extension:

  * `POST /applications/{application_uuid}/calls`
  * `POST /applications/{application_uuid}/nodes/{node_uuid}/calls`
  * `POST /faxes/create`
  * `POST /users/me/faxes/create`
  * `POST /transfers`
  * `POST /users/me/transfers`

## 21.01

* New attribute for `calls` objects (API and events):

  * `record_state`

* New API to start recording calls

  * `PUT /calls/{call_id}/record/start`
  * `PUT /users/me/calls/{call_id}/record/start`

* New API to stop recording calls

  * `PUT /calls/{call_id}/record/stop`
  * `PUT /users/me/calls/{call_id}/record/stop`

## 20.13

* New attribute for `calls` objects (API and events):

  * `line_id`

## 20.12

* New API to create adhoc conferences

  * `POST /users/me/conferences/adhoc`
  * `DELETE /users/me/conferences/adhoc`
  * `PUT /users/me/conferences/adhoc/{adhoc_conference_id}/participants/{call_id}`
  * `DELETE /users/me/conferences/adhoc/{adhoc_conference_id}/participants/{call_id}`

* New events for adhoc conferences:

  * `adhoc_conference_created`
  * `adhoc_conference_deleted`
  * `adhoc_conference_participant_joined`
  * `adhoc_conference_participant_left`

* New API to answer calls

  * `PUT /calls/{call_id}/answer`
  * `PUT /user/me/calls/{call_id}/answer`

## 20.11

* New API to hold calls

  * `PUT /calls/{call_id}/hold/start`
  * `PUT /calls/{call_id}/hold/stop`
  * `PUT /users/me/calls/{call_id}/hold/start`
  * `PUT /users/me/calls/{call_id}/hold/stop`

## 20.10

* The event `call_updated` is sent to all conference participants when a new participant joins.

## 20.08

* Deprecate SSL configuration
* New API to check if voicemail greeting exists

  * `HEAD /voicemails/{voicemail_id}/greetings/<greeting>`
  * `HEAD /users/me/voicemails/{voicemail_id}/greetings/<greeting>`

* New API to simulate a user pressing DTMF keys

  * `PUT /calls/{call_id}/dtmf`
  * `PUT /users/me/calls/{call_id}/dtmf`

* New API to simulate a user pressing DTMF keys inside an application

  * `PUT /applications/{application_uuid}/calls/{call_id}/dtmf`

## 20.03

* New attribute `all_lines` in routes:

  * `POST /calls`
  * `POST /users/me/calls`

* New event `call_answered` is sent when a call is answered.
* New attribute `auto_answer` in routes:

  * `POST /calls`
  * `POST /relocates`

* New attribute `auto_answer_caller` in route `POST /users/me/calls`

## 20.02

* New attribute `muted` for Call objects in routes:

  * `GET,POST /calls`
  * `GET /calls/{call_id}`
  * `GET,POST /users/me/calls`

* New API to mute calls

  * `PUT /calls/{call_id}/mute/start`
  * `PUT /calls/{call_id}/mute/stop`
  * `PUT /users/me/calls/{call_id}/mute/start`
  * `PUT /users/me/calls/{call_id}/mute/stop`

## 20.01

* Configuration `startup_connection_tries` has been removed

* The following endpoint has been added to list the status of lines

  * `GET /1.0/lines`

## 19.17

* The following endpoint has been added to list the status of trunks

  * `GET /1.0/trunks`

## 19.10

* The following endpoints have a new query parameter `line_id` to select a line

  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/queue/{call_id}/answer`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}/answer`

* New API for calling users into applications:

  * POST `/1.0/applications/{uuid}/nodes/{node_uuid}/calls/users`

* New API for answering a call inside an application:

  * PUT `/1.0/applications/{uuid}/calls/{call_id}/answer`
  * PUT `/1.0/applications/{uuid}/calls/{call_id}/progress/start`
  * PUT `/1.0/applications/{uuid}/calls/{call_id}/progress/stop`

## 19.09

* The following endpoints now have Wazo-Tenant header to support multi-tenant

  * `GET /1.0/switchboards/{switchboard_uuid}/calls/held`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}/answer`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}`
  * `GET /1.0/switchboards/{switchboard_uuid}/calls/queued`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/queued/{call_id}/answer`

* The `sip_call_id` field has been added to the calls response and events

## 19.05

* The following endpoints have been moved to wazo-chatd and deleted from wazo-calld:

  * POST `/1.0/chats`
  * POST `/1.0/users/me/chats`
  * GET `/1.0/users/me/chats`

## 19.04

* New API for faxes:

  * `POST /faxes`
  * `POST /users/me/faxes`

* The following endpoints have been moved to wazo-chatd and deleted from wazo-calld:

  * GET `/1.0/lines/{id}/presences`

  * GET `/1.0/users/{uuid}/presences`
  * PUT `/1.0/users/{uuid}/presences`

  * GET `/1.0/users/me/presences`
  * PUT `/1.0/users/me/presences`

  * GET `/1.0/users/me/calls`
  * DELETE `/1.0/users/me/calls/{id}`

## 19.03

* New API for conferences:

  * `POST /conferences/{conference_id}/record`
  * `DELETE /conferences/{conference_id}/record`

* Modification of conference mute API:

  * `PUT /conferences/{conference_id}/participants/{participant_id}/mute`
  * `PUT /conferences/{conference_id}/participants/{participant_id}/unmute`

## 19.02

* New API for conferences:

  * `GET /conferences/{conference_id}/participants`
  * `DELETE /conferences/{conference_id}/participants/{participant_id}`
  * `POST /conferences/{conference_id}/participants/{participant_id}/mute`
  * `DELETE /conferences/{conference_id}/participants/{participant_id}/mute`

## 19.01

* Add the ability to specify a PJSIP contact on relocates using the `contact` field in the line location body

  * `POST /users/me/relocates`

## 18.14

* Channel variables can now be specified on the following resources

  * `POST /applications/{application_uuid}/calls`
  * `POST /applications/{application_uuid}/nodes/{node_uuid}/calls`

* The displayed caller id name and number can be specified on the following resources

  * `POST /applications/{application_uuid}/calls`
  * `POST /applications/{application_uuid}/nodes/{node_uuid}/calls`

## 18.12

* The body of endpoint `GET /status` has been added a new subkey `status`.
* The applications calls now contain the snoop fields which list snoop membership

## 18.11

* New API to start and stop music on hold on a call in an application

  * `PUT /applications/{application_uuid}/calls/{call_id}/moh/{moh_uuid}/start`
  * `PUT /applications/{application_uuid}/calls/{call_id}/moh/stop`

* New API to place a call on hold and resume it

  * `PUT /applications/{application_uuid}/calls/{call_id}/hold/start`
  * `PUT /applications/{application_uuid}/calls/{call_id}/hold/stop`

* New API to snoop on calls

  * `GET /applications/{application_uuid}/snoops`
  * `POST /applications/{application_uuid}/calls/{call_id}/snoop`
  * `PUT /applications/{application_uuid}/snoops/{snoop_uuid}`
  * `GET /applications/{application_uuid}/snoops/{snoop_uuid}`
  * `DELETE /applications/{application_uuid}/snoops/{snoop_uuid}`

* New API to mute calls

  * `PUT /applications/{application_uuid}/calls/{call_id}/mute/start`
  * `PUT /applications/{application_uuid}/calls/{call_id}/mute/stop`

## 18.10

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

## 17.17

* New API for relocating calls:

  * `PUT /users/me/relocates/{relocate_uuid}/cancel`

* New field for calls:

  * `dialed_extension`

## 17.15

* New APIs for relocating calls:

  * `GET,POST /users/me/relocates`
  * `GET /users/me/relocates/{relocate_uuid}`
  * `PUT /users/me/relocates/{relocate_uuid}/complete`

## 17.12

* A new API for getting chat history:

  * GET `/1.0/users/me/chats`

## 17.05

* New attribute `is_caller` for Call objects in routes:

  * `GET,POST /calls`
  * `GET /calls/{call_id}`
  * `GET,POST /users/me/calls`

## 17.03

* New routes for switchboard operations. This is not (yet) related to the current switchboard
  implementation.

  * `GET /1.0/switchboards/{switchboard_uuid}/calls/held`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/held/{call_id}/answer`

## 17.02

* A new API for switchboard operations. This is not (yet) related to the current switchboard
  implementation.

  * `GET /1.0/switchboards/{switchboard_uuid}/calls/queued`
  * `PUT /1.0/switchboards/{switchboard_uuid}/calls/queued/{call_id}/answer`

## 17.01

* A new parameter for call creation (`POST /calls` and `POST /users/me/calls`)

  * `from_mobile`

## 16.16

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

## 16.11

* A new API for getting the status of lines:

  * GET `/1.0/lines/{id}/presences`

## 16.10

* A new API for checking the status of the daemon:

  * GET `/1.0/status`

## 16.09

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

## 16.08

* A new API for making calls from the authenticated user:

  * POST `/1.0/users/me/calls`

* A new API for sending chat messages:

  * POST `/1.0/chats`
  * POST `/1.0/users/me/chats`

* A new parameter for transfer creation (POST `/1.0/transfers`):

  * `variables`

* A new API for making transfers from the authenticated user:

  * POST `/1.0/users/me/transfers`
