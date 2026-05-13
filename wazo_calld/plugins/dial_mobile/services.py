# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import requests
from ari.exceptions import ARINotFound, ARIServerError
from requests import HTTPError, RequestException

from wazo_calld.plugin_helpers.ari_ import Bridge

logger = logging.getLogger(__name__)


@dataclass
class IncomingCallPending:
    """Push notification not yet sent — initial state."""

    call_id: str
    tenant_uuid: str
    user_uuid: str
    origin_call_id: str
    payload: dict

    def notified(self) -> 'IncomingCallNotified':
        return IncomingCallNotified(
            call_id=self.call_id,
            tenant_uuid=self.tenant_uuid,
            user_uuid=self.user_uuid,
            origin_call_id=self.origin_call_id,
            payload=self.payload,
        )


@dataclass
class IncomingCallNotified(IncomingCallPending):
    """Push sent; waiting for mobile app to register and answer."""

    def received(self) -> 'IncomingCallReceived':
        return IncomingCallReceived(
            call_id=self.call_id,
            tenant_uuid=self.tenant_uuid,
            user_uuid=self.user_uuid,
            origin_call_id=self.origin_call_id,
            payload=self.payload,
        )

    def cancelled(self) -> 'IncomingCallCancelled':
        return IncomingCallCancelled(
            call_id=self.call_id,
            tenant_uuid=self.tenant_uuid,
            user_uuid=self.user_uuid,
            origin_call_id=self.origin_call_id,
            payload=self.payload,
        )


@dataclass
class IncomingCallReceived(IncomingCallNotified):
    """Mobile answered the call — terminal, no push cancellation sent."""


@dataclass
class IncomingCallCancelled(IncomingCallNotified):
    """Caller hung up or PSTN fallback committed — terminal, push cancellation sent."""


IncomingCall = IncomingCallPending | IncomingCallNotified


@dataclass(eq=False)
class PSTNFallbackPending:
    """Timer armed; PSTN fallback may fire when it expires."""

    call_id: str
    timer: threading.Timer

    def triggering(self) -> 'PSTNFallbackTriggering':
        return PSTNFallbackTriggering(call_id=self.call_id)

    def cancelled(self) -> 'PSTNFallbackCancelled':
        return PSTNFallbackCancelled(call_id=self.call_id)


@dataclass(eq=False)
class PSTNFallbackTriggering:
    """Timer fired; commit (cancel-push + originate) in flight.

    Observable phase marker between `Pending` and `Dialing`. The
    transition into and out of this state is serialised by the
    per-call lock held by `_pstn_fallback`.
    """

    call_id: str

    def dialing(self, channel_id: str) -> 'PSTNFallbackDialing':
        return PSTNFallbackDialing(call_id=self.call_id, channel_id=channel_id)

    def cancelled(self) -> 'PSTNFallbackCancelled':
        return PSTNFallbackCancelled(call_id=self.call_id)


@dataclass(eq=False)
class PSTNFallbackDialing:
    """PSTN leg has been originated, pending answer from destination"""

    call_id: str
    channel_id: str

    def answered(self) -> 'PSTNFallbackDialAnswered':
        return PSTNFallbackDialAnswered(
            call_id=self.call_id, channel_id=self.channel_id
        )

    def cancelled(self) -> 'PSTNFallbackCancelled':
        return PSTNFallbackCancelled(call_id=self.call_id)


@dataclass(eq=False)
class PSTNFallbackDialAnswered:
    """Terminal — the PSTN leg answered and joined the bridge with the
    caller."""

    call_id: str
    channel_id: str


@dataclass(eq=False)
class PSTNFallbackCancelled:
    """Terminal — fallback was cancelled or completed without dialing."""

    call_id: str


class _PSTNFallbackAbort(Exception):
    """Internal control-flow signal: raised inside `_pstn_fallback` for
    any early exit from the slow path so the surrounding `except`
    transitions Triggering → Cancelled."""


PSTNFallback = (
    PSTNFallbackPending
    | PSTNFallbackTriggering
    | PSTNFallbackDialing
    | PSTNFallbackDialAnswered
    | PSTNFallbackCancelled
)


PSTN_FALLBACK_MIN_TIMEOUT = 10.0
PSTN_FALLBACK_RING_TIMEOUT_FACTOR = 0.5


class _NoSuchChannel(Exception):
    pass


class _PollingContactDialer:
    def __init__(
        self,
        ari,
        future_bridge_uuid,
        channel_id,
        aor,
        ringing_time,
        pickup_mark,
        on_contact_dialed: Callable[[], None] | None = None,
    ):
        self._ari = ari
        self.future_bridge_uuid = future_bridge_uuid
        self.should_stop = threading.Event()
        self._thread = threading.Thread(
            name='PollingContactDialer',
            target=self._run_no_exception,
            args=(channel_id, aor),
        )
        self._called_contacts: set[str] = set()
        self.is_running = False
        self._dialed_channels: set = set()
        self._caller_channel_id = channel_id
        self._ringing_time = ringing_time
        self.pickup_mark = pickup_mark
        self._on_contact_dialed = on_contact_dialed
        self._wakeup = threading.Event()

        dialer_id = str(self)

        class CustomAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                return f'{dialer_id}: {msg}', kwargs

        self.logger = CustomAdapter(logging.getLogger(__name__), {})

    def __str__(self) -> str:
        return f'Dialer({self.future_bridge_uuid}, {self._caller_channel_id})'

    def start(self):
        self.logger.debug('Starting')
        self._thread.start()

    def stop(self):
        if not self._thread.is_alive():
            return

        self.logger.debug('Stopping')
        self.should_stop.set()
        self._wakeup.set()
        self._thread.join()
        self.logger.debug('Stopped')

    def kick(self) -> None:
        """Wake the run loop to re-check contacts."""
        self._wakeup.set()

    def _run_no_exception(self, *args, **kwargs):
        try:
            return self._run(*args, **kwargs)
        except Exception:
            self.logger.exception('Unhandled exception in %s thread', self._thread.name)

    def _run(self, channel_id, aor):
        channel = self._ari.channels.get(channelId=channel_id)
        caller_id = '"{name}" <{number}>'.format(**channel.json['caller'])

        # Initial check: contact may already be registered when the call lands.
        self._dial_current_contacts(channel_id, aor, caller_id)

        while not self.should_stop.is_set():
            self._wakeup.wait()
            self._wakeup.clear()

            if self.should_stop.is_set():
                break

            if not self._channel_is_up(channel_id):
                self.logger.debug(
                    'calling channel %s is gone: stopping %s thread',
                    channel_id,
                    self._thread.name,
                )
                break

            self.logger.debug('woke up for new contacts')
            self._dial_current_contacts(channel_id, aor, caller_id)

        self.logger.debug('Interrupted run loop')
        self._remove_unanswered_channels()

    def _dial_current_contacts(self, channel_id, aor, caller_id):
        for contact in self._get_contacts(channel_id, aor):
            if self.should_stop.is_set():
                break
            self._send_contact_to_current_call(
                contact, self.future_bridge_uuid, caller_id
            )

    def _channel_is_up(self, channel_id):
        try:
            self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            return False
        else:
            return True

    def _send_contact_to_current_call(self, contact, future_bridge_uuid, caller_id):
        if contact in self._called_contacts:
            return

        self.logger.debug(
            'sending %s to the future bridge %s', contact, future_bridge_uuid
        )
        channel = self._ari.channels.originate(
            endpoint=contact,
            app='dial_mobile',
            appArgs=['join', future_bridge_uuid],
            callerId=caller_id,
            originator=self._caller_channel_id,
            timeout=self._ringing_time,
        )

        self.logger.debug('Dialed channel %s', channel.id)
        self._called_contacts.add(contact)
        self._dialed_channels.add(channel)
        if self._on_contact_dialed is not None:
            self._on_contact_dialed()

    def _remove_unanswered_channels(self):
        for channel in self._dialed_channels:
            try:
                channel_info = channel.get()
                if channel_info.json['state'] == 'Up':
                    continue
                self._ari.channels.hangup(channelId=channel.id)
            except ARINotFound:
                continue  # The channel has already been hung up

    def _get_contacts(self, channel_id, aor):
        asterisk_dialplan_function = f'PJSIP_DIAL_CONTACTS({aor})'
        try:
            response = self._ari.channels.getChannelVar(
                channelId=channel_id,
                variable=asterisk_dialplan_function,
            )
            return [contact for contact in response['value'].split('&') if contact]
        except ARINotFound:
            return []

    def _on_channel_gone(self, channel_id):
        self.logger.debug(
            'Channel gone %s, dialed %d channels',
            channel_id,
            len(self._dialed_channels),
        )
        dialed_channel_ids = {channel.id for channel in self._dialed_channels}
        if (
            channel_id not in dialed_channel_ids
            and channel_id != self._caller_channel_id
        ):
            raise _NoSuchChannel(channel_id)

        # call was refused, stop ringing and hangup
        self.logger.debug(
            'Caller or dialed channel %s is gone, stopping dialer...', channel_id
        )
        self.stop()
        if channel_id != self._caller_channel_id:
            self.logger.debug(
                'Call was refused, hanging up caller channel %s', channel_id
            )
            try:
                self._ari.channels.hangup(
                    channelId=self._caller_channel_id, reason_code=21
                )
            except ARINotFound:
                pass  # Already gone


class DialMobileService:
    def __init__(self, ari, notifier, amid_client, auth_client, confd_client):
        self._ari = ari.client
        self._auth_client = auth_client
        self._amid_client = amid_client
        self._confd_client = confd_client
        self._contact_dialers = {}
        self._dialers_by_aor: dict[str, set[_PollingContactDialer]] = {}
        self._caller_channel_leg_by_bridge = {}
        self._call_ring_time = {}
        self._incoming_calls: dict[str, IncomingCall] = {}
        self._notifier = notifier
        self._pstn_fallbacks: dict[str, PSTNFallback] = {}
        self._call_locks: dict[str, threading.RLock] = {}
        self._origin_call_id_by_bridge_uuid: dict[str, str] = {}
        self._bridge_uuid_by_origin_call_id: dict[str, str] = {}
        self._call_id_by_origin_call_id: dict[str, str] = {}

    def find_bridge_by_exten_context(self, exten, context):
        pickup_mark = f'{exten}%{context}'
        for bridge_uuid, dialer in self._contact_dialers.items():
            if dialer.pickup_mark == pickup_mark:
                return bridge_uuid

    def dial_all_contacts(self, caller_channel_id, origin_channel_id, aor):
        self._ari.channels.ring(channelId=caller_channel_id)

        logger.info('dial_all_contacts(%s, %s)', caller_channel_id, aor)
        future_bridge_uuid = str(uuid.uuid4())

        logger.debug(
            '%s is waiting for a channel to join the bridge %s',
            caller_channel_id,
            future_bridge_uuid,
        )
        ringing_time = self._call_ring_time.get(origin_channel_id, 30)
        try:
            pickup_mark = self._ari.channels.getChannelVar(
                channelId=caller_channel_id,
                variable=f'PJSIP_ENDPOINT({aor},PICKUPMARK)',
            )['value']
        except ARIServerError as e:
            logger.warning('PJSIP_ENDPOINT(%s,PICKUPMARK) lookup failed: %s', aor, e)
            pickup_mark = ''

        def _on_contact_dialed() -> None:
            # The mobile has registered and the SIP INVITE has been sent;
            # the PSTN fallback is no longer needed.
            if call_id := self._call_id_for_bridge(future_bridge_uuid):
                logger.debug(
                    'mobile contact dialed for call %s: cancelling PSTN fallback',
                    call_id,
                )
                self._cancel_pstn_fallback(call_id)

        dialer = _PollingContactDialer(
            self._ari,
            future_bridge_uuid,
            caller_channel_id,
            aor,
            ringing_time,
            pickup_mark,
            on_contact_dialed=_on_contact_dialed,
        )
        self._contact_dialers[future_bridge_uuid] = dialer
        self._dialers_by_aor.setdefault(aor, set()).add(dialer)
        self._caller_channel_leg_by_bridge[future_bridge_uuid] = caller_channel_id
        self._origin_call_id_by_bridge_uuid[future_bridge_uuid] = origin_channel_id
        self._bridge_uuid_by_origin_call_id[origin_channel_id] = future_bridge_uuid
        dialer.start()

    def notify_contact_available(self, aor: str) -> None:
        logger.debug('new contact available for monitored aor %s', aor)
        for dialer in self._dialers_by_aor.get(aor, set()):
            dialer.kick()

    def _unregister_dialer_by_aor(self, dialer: _PollingContactDialer) -> None:
        for aor, dialers in list(self._dialers_by_aor.items()):
            dialers.discard(dialer)
            if not dialers:
                self._dialers_by_aor.pop(aor, None)

    def join_bridge(self, channel_id, future_bridge_uuid):
        logger.info('%s is joining bridge %s', channel_id, future_bridge_uuid)
        call_id = self._call_id_for_bridge(future_bridge_uuid)
        if call_id and (lock := self._call_locks.get(call_id)):
            with lock:
                match self._pstn_fallbacks.get(call_id):
                    case PSTNFallbackDialing(channel_id=cid) as current if (
                        cid == channel_id
                    ):
                        # PSTN leg itself answering — success.
                        logger.debug('pstn fallback call %s joining bridge', call_id)
                        self._pstn_fallbacks[call_id] = current.answered()
                    case None | PSTNFallbackCancelled() | (PSTNFallbackDialAnswered()):
                        # Terminal: nothing to do.
                        pass
                    case _:
                        # Different channel / non-Dialing state — cancel.
                        logger.debug('cancelling pstn fallback for call %s', call_id)
                        self._cancel_pstn_fallback(call_id)

        dialer = self._contact_dialers.pop(future_bridge_uuid, None)
        if dialer:
            logger.debug('Removing dialer: %s', str(dialer))
            self._unregister_dialer_by_aor(dialer)
            dialer.stop()
        else:
            # No active dialer means the call was already cancelled or answered;
            # this channel arrived late and has no bridge to join — hang it up.
            if call_id:
                incoming = self._incoming_calls.get(call_id)
                if incoming is not None:
                    logger.warning(
                        'join_bridge(channel_id=%s, future_bridge_uuid=%s): call %s: '
                        'bridge has no dialer but push state is %s; '
                        'hanging up late channel',
                        channel_id,
                        future_bridge_uuid,
                        call_id,
                        type(incoming).__name__,
                    )
                else:
                    logger.debug(
                        'join_bridge: bridge %s has no dialer, call %s already'
                        ' cleaned up; hanging up late channel %s',
                        future_bridge_uuid,
                        call_id,
                        channel_id,
                    )
            try:
                self._ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                pass
            return

        outgoing_channel_id = self._caller_channel_leg_by_bridge.get(future_bridge_uuid)
        try:
            try:
                self._ari.channels.answer(channelId=outgoing_channel_id)
            except ARINotFound:
                logger.info(
                    'the caller (%s) left the call before being bridged',
                    outgoing_channel_id,
                )
                try:
                    self._ari.channels.hangup(channelId=channel_id)
                except ARINotFound:
                    # If its already gone do nothing
                    pass
                if call_id:
                    self.cancel_push_mobile(call_id)
                return

            try:
                self._ari.channels.answer(channelId=channel_id)
            except ARINotFound:
                logger.info(
                    'the answered (%s) left the call before being bridged',
                    channel_id,
                )
                return

            bridge = self._ari.bridges.createWithId(
                type='mixing',
                bridgeId=f'wazo-dial-mobile-{future_bridge_uuid}',
            )
            # Without the inhibitConnectedLineUpdates everyone in the bridge will receive a new
            # connected line update with the caller ID of the caller when PAI is trusted, including
            # the caller...
            bridge.addChannel(channel=channel_id, inhibitConnectedLineUpdates=True)
            bridge.addChannel(
                channel=outgoing_channel_id, inhibitConnectedLineUpdates=True
            )
        finally:
            self._prune_call_state(future_bridge_uuid)

    def _call_id_for_bridge(self, bridge_uuid: str) -> str | None:
        origin_call_id = self._origin_call_id_by_bridge_uuid.get(bridge_uuid)
        return (
            self._call_id_by_origin_call_id.get(origin_call_id)
            if origin_call_id
            else None
        )

    def _prune_call_state(self, future_bridge_uuid: str) -> None:
        # Tear down per-call indirection so the maps don't grow unbounded
        # across the lifetime of the service.
        origin_call_id = self._origin_call_id_by_bridge_uuid.pop(
            future_bridge_uuid, None
        )
        if origin_call_id is not None:
            self._bridge_uuid_by_origin_call_id.pop(origin_call_id, None)
            call_id = self._call_id_by_origin_call_id.pop(origin_call_id, None)
            self._call_ring_time.pop(origin_call_id, None)
            if call_id is not None:
                self._pstn_fallbacks.pop(call_id, None)
                self._call_locks.pop(call_id, None)
        self._caller_channel_leg_by_bridge.pop(future_bridge_uuid, None)

    def notify_channel_gone(self, channel_id):
        # If a PSTN-fallback channel has torn down on its own, transition
        # its state to Cancelled so it isn't double-hung-up later.
        for tracked_call_id, state in list(self._pstn_fallbacks.items()):
            match state:
                case PSTNFallbackDialing(channel_id=cid) if cid == channel_id:
                    self._pstn_fallbacks[tracked_call_id] = state.cancelled()

        to_remove: list[tuple[str, bool]] = []

        for key, dialer in self._contact_dialers.items():
            try:
                dialer._on_channel_gone(channel_id)
            except _NoSuchChannel:
                continue
            else:
                is_caller_gone = channel_id == dialer._caller_channel_id
                to_remove.append((key, is_caller_gone))

        for key, is_caller_gone in to_remove:
            dialer = self._contact_dialers[key]
            logger.debug('Removing dialer: %s', str(dialer))
            del self._contact_dialers[key]
            self._unregister_dialer_by_aor(dialer)
            if call_id := self._call_id_for_bridge(key):
                if is_caller_gone:
                    logger.debug(
                        'Caller channel gone for call %s: cancelling PSTN fallback',
                        call_id,
                    )
                else:
                    logger.debug(
                        'Dialed mobile contact gone for call %s: '
                        'mobile was reachable, cancelling PSTN fallback',
                        call_id,
                    )
                self._cancel_pstn_fallback(call_id)
                self.cancel_push_mobile(call_id)
            self._prune_call_state(key)

    def clean_bridge(self, bridge_id):
        bridge_helper = Bridge(bridge_id, self._ari)
        if bridge_helper.has_lone_channel():
            logger.debug(
                'dial_mobile: bridge %s: only one participant left, hanging up',
                bridge_id,
            )
            bridge_helper.hangup_all()
        elif bridge_helper.is_empty():
            logger.debug(
                'dial_mobile bridge %s: bridge is empty, destroying', bridge_id
            )
            try:
                self._ari.bridges.destroy(bridgeId=bridge_id)
            except ARINotFound:
                pass

    def on_calld_stopping(self):
        for dialer in self._contact_dialers.values():
            dialer.stop()
        # Cancel any armed PSTN fallback timers so the (non-daemon) Timer
        # threads do not block process exit, and the callback doesn't run
        # against half-torn-down clients.
        for state in self._pstn_fallbacks.values():
            match state:
                case PSTNFallbackPending(timer=timer):
                    timer.cancel()
        self._pstn_fallbacks.clear()

    def _set_user_hint(self, user_uuid, has_mobile_sessions):
        self._amid_client.action(
            'Setvar',
            {
                'Variable': f'DEVICE_STATE(Custom:{user_uuid}-mobile)',
                'Value': 'NOT_INUSE' if has_mobile_sessions else 'UNAVAILABLE',
            },
        )

    def on_mobile_refresh_token_created(self, user_uuid):
        self._set_user_hint(user_uuid, True)

    def on_mobile_refresh_token_deleted(self, user_uuid):
        try:
            response = self._auth_client.token.list(user_uuid, mobile=True)
        except requests.HTTPError as e:
            logger.error(
                'failed to check if user %s still has a mobile refresh token: %s: %s',
                user_uuid,
                type(e).__name__,
                e,
            )
            return

        mobile = response['filtered'] > 0
        self._set_user_hint(user_uuid, mobile)

    def send_push_notification(
        self,
        tenant_uuid,
        user_uuid,
        call_id,
        sip_call_id,
        caller_id_name,
        caller_id_number,
        video_enabled,
        ring_timeout,
        origin_call_id,
        push_mobile_timestamp,
    ):
        payload = {
            'peer_caller_id_number': caller_id_number,
            'peer_caller_id_name': caller_id_name,
            'call_id': call_id,
            'video': video_enabled,
            'ring_timeout': ring_timeout,
            'sip_call_id': sip_call_id,
            'mobile_wakeup_timestamp': push_mobile_timestamp,
        }

        pending = IncomingCallPending(
            call_id=call_id,
            tenant_uuid=tenant_uuid,
            user_uuid=user_uuid,
            origin_call_id=origin_call_id,
            payload=payload,
        )
        self._incoming_calls[call_id] = pending

        self._call_ring_time[origin_call_id] = ring_timeout
        self._call_id_by_origin_call_id[origin_call_id] = call_id

        if self._pstn_fallback_eligible(user_uuid, tenant_uuid):
            fallback_timeout = max(
                PSTN_FALLBACK_MIN_TIMEOUT,
                PSTN_FALLBACK_RING_TIMEOUT_FACTOR * int(ring_timeout),
            )
            timer = threading.Timer(
                fallback_timeout, self._pstn_fallback, args=[call_id]
            )
            self._call_locks[call_id] = threading.RLock()
            self._pstn_fallbacks[call_id] = PSTNFallbackPending(
                call_id=call_id, timer=timer
            )
            timer.start()

        self._notifier.push_notification(payload, tenant_uuid, user_uuid)
        self._incoming_calls[call_id] = pending.notified()

    def _pstn_fallback_eligible(self, user_uuid: str, tenant_uuid: str) -> bool:
        # Check user config once at push time so we don't arm a timer that
        # would no-op when it fires.  On confd errors we err on the safe side
        # and arm the timer anyway so the existing in-`_pstn_fallback` checks
        # can re-evaluate when the timer fires.
        try:
            user = self._confd_client.users.get(user_uuid, tenant_uuid=tenant_uuid)
        except (HTTPError, RequestException) as e:
            logger.warning(
                'PSTN fallback eligibility lookup failed for user %s: %s; '
                'arming fallback timer optimistically',
                user_uuid,
                e,
            )
            return True
        return bool(
            user.get('mobile_fallback_enabled') and user.get('mobile_phone_number')
        )

    def _cancel_pstn_fallback(self, call_id: str) -> None:
        lock = self._call_locks.get(call_id)
        if lock is None:
            return
        with lock:
            match self._pstn_fallbacks.get(call_id):
                case None | PSTNFallbackCancelled() | PSTNFallbackDialAnswered():
                    return
                case PSTNFallbackPending(timer=timer) as current:
                    timer.cancel()
                    self._pstn_fallbacks[call_id] = current.cancelled()
                case PSTNFallbackDialing(channel_id=channel_id) as current:
                    self._hangup_pstn_channel(channel_id)
                    self._pstn_fallbacks[call_id] = current.cancelled()
                case PSTNFallbackTriggering() as current:
                    # `_pstn_fallback` is in its (lock-free) Phase 2 —
                    # confd lookups and channel checks. Marking the state
                    # Cancelled tells the Phase 3 re-check to abort.
                    logger.debug(
                        'cancelling PSTN fallback for call %s while in ' 'Triggering',
                        call_id,
                    )
                    self._pstn_fallbacks[call_id] = current.cancelled()

    def _hangup_pstn_channel(self, channel_id: str) -> None:
        try:
            self._ari.channels.hangup(channelId=channel_id)
        except ARINotFound:
            pass

    def cancel_push_mobile(self, call_id: str) -> None:
        incoming_call = self._incoming_calls.pop(call_id, None)
        match incoming_call:
            case IncomingCallNotified():
                self._notifier.cancel_push_notification(
                    incoming_call.payload,
                    incoming_call.tenant_uuid,
                    incoming_call.user_uuid,
                )
            case None:
                logger.warning(
                    'cancel_push_mobile: no incoming call for call_id %s', call_id
                )
            case _:
                logger.warning(
                    'cancel_push_mobile: unexpected state %s for call_id %s',
                    type(incoming_call).__name__,
                    call_id,
                )

    def complete_pending_push_mobile(self, call_id: str) -> None:
        incoming_call = self._incoming_calls.pop(call_id, None)
        match incoming_call:
            case IncomingCallNotified():
                pass
            case None:
                logger.warning(
                    'complete_pending_push_mobile: no incoming call for call_id %s',
                    call_id,
                )
            case _:
                logger.warning(
                    'complete_pending_push_mobile: unexpected state %s for call_id %s',
                    type(incoming_call).__name__,
                    call_id,
                )

    def _pstn_fallback(self, call_id: str) -> None:
        """Timer-fired callback. Drives the fallback through:
        Pending → Triggering (early) → Dialing on success, or
        → Cancelled on any preliminary failure / originate failure /
        racing cancel.
        """
        lock = self._call_locks.get(call_id)
        if lock is None:
            logger.warning(
                'PSTN fallback timer fired for call %s but no lock available, '
                'aborting',
                call_id,
            )
            return

        # Phase 1: transition Pending → Triggering atomically. From here
        # on, observers (e.g. `_cancel_pstn_fallback`) see Triggering.
        with lock:
            match self._pstn_fallbacks.get(call_id):
                case PSTNFallbackPending() as current:
                    self._pstn_fallbacks[call_id] = current.triggering()
                case _ as state:
                    logger.debug(
                        'PSTN fallback for call %s not in Pending (got %s); '
                        'aborting',
                        call_id,
                        type(state).__name__,
                    )
                    return

        # Phase 2: slow path (confd lookups, channel checks). No lock
        # held; state is observably Triggering. Any early exit raises
        # `_PSTNFallbackAbort`, which the handler turns into a
        # Triggering → Cancelled transition.
        try:
            pending = self._incoming_calls.get(call_id)
            if not pending:
                logger.info(
                    "no pending push for call_id %s, aborting PSTN fallback",
                    call_id,
                )
                raise _PSTNFallbackAbort

            try:
                user = self._confd_client.users.get(
                    pending.user_uuid, tenant_uuid=pending.tenant_uuid
                )
            except (HTTPError, RequestException) as e:
                logger.error(
                    'PSTN fallback: cannot fetch user %s: %s',
                    pending.user_uuid,
                    e,
                )
                raise _PSTNFallbackAbort from e

            if not user.get('mobile_fallback_enabled'):
                logger.info(
                    'PSTN fallback: user %s has mobile fallback disabled, skipping',
                    pending.user_uuid,
                )
                raise _PSTNFallbackAbort

            mobile_phone_number = user.get('mobile_phone_number')
            if not mobile_phone_number:
                logger.info(
                    'PSTN fallback: user %s has no mobile_phone_number, skipping',
                    pending.user_uuid,
                )
                raise _PSTNFallbackAbort

            lines = user.get('lines', [])
            if not lines:
                logger.warning(
                    'PSTN fallback: user %s has no lines, skipping',
                    pending.user_uuid,
                )
                raise _PSTNFallbackAbort

            try:
                line = self._confd_client.lines.get(
                    lines[0]['id'], tenant_uuid=pending.tenant_uuid
                )
            except (HTTPError, RequestException) as e:
                logger.error(
                    'PSTN fallback: cannot fetch line for user %s: %s',
                    pending.user_uuid,
                    e,
                )
                raise _PSTNFallbackAbort from e

            user_context = line['context']

            future_bridge_uuid = self._bridge_uuid_by_origin_call_id.get(
                pending.origin_call_id
            )
            if not future_bridge_uuid:
                logger.warning(
                    'PSTN fallback: no bridge found for call %s, skipping',
                    call_id,
                )
                raise _PSTNFallbackAbort

            caller_channel_id = self._caller_channel_leg_by_bridge.get(
                future_bridge_uuid
            )
            try:
                self._ari.channels.get(channelId=caller_channel_id)
            except ARINotFound as e:
                logger.info(
                    'PSTN fallback: caller channel %s already gone for call %s, '
                    'skipping',
                    caller_channel_id,
                    call_id,
                )
                raise _PSTNFallbackAbort from e

            caller_id = '"{name}" <{number}>'.format(
                name=pending.payload['peer_caller_id_name'],
                number=pending.payload['peer_caller_id_number'],
            )

            # Phase 3: commit (cancel-push + originate). Re-check the
            # state under the lock — a racing cancel may have transitioned
            # us to Cancelled during phase 2.
            with lock:
                match self._pstn_fallbacks.get(call_id):
                    case PSTNFallbackTriggering() as triggering:
                        logger.info(
                            'PSTN fallback: originating Local/%s@%s for user %s '
                            '(call %s)',
                            mobile_phone_number,
                            user_context,
                            pending.user_uuid,
                            call_id,
                        )
                        self.cancel_push_mobile(call_id)
                        try:
                            pstn_channel = self._ari.channels.originate(
                                endpoint=(
                                    f'Local/{mobile_phone_number}@{user_context}'
                                ),
                                app='dial_mobile',
                                appArgs=['join', future_bridge_uuid],
                                callerId=caller_id,
                                originator=caller_channel_id,
                                variables={
                                    'variables': {
                                        '_WAZO_TENANT_UUID': pending.tenant_uuid
                                    }
                                },
                            )
                        except (
                            ARIServerError,
                            HTTPError,
                            RequestException,
                        ) as e:
                            logger.exception(
                                'PSTN fallback: originate failed for call %s; '
                                'leaving fallback Cancelled',
                                call_id,
                            )
                            raise _PSTNFallbackAbort from e
                        self._pstn_fallbacks[call_id] = triggering.dialing(
                            pstn_channel.id
                        )
                    case _ as state:
                        logger.debug(
                            'PSTN fallback for call %s no longer in Triggering '
                            '(got %s); not originating',
                            call_id,
                            type(state).__name__,
                        )
        except _PSTNFallbackAbort:
            # Transition Triggering → Cancelled if we still own that state.
            with lock:
                match self._pstn_fallbacks.get(call_id):
                    case PSTNFallbackTriggering() as triggering:
                        self._pstn_fallbacks[call_id] = triggering.cancelled()
                    case _ as state:
                        # already cancelled
                        logger.debug(
                            'PSTN fallback aborted but state already %s', state
                        )
                        return

    def has_a_registered_mobile_and_pending_push(
        self, push_call_id, call_id, endpoint, user_uuid
    ):
        pending_push = self._incoming_calls.get(push_call_id)
        if not pending_push:
            return False

        if user_uuid != pending_push.user_uuid:
            return False

        raw_contacts = self._ari.channels.getChannelVar(
            channelId=call_id,
            variable=f'PJSIP_AOR({endpoint},contact)',
        )['value']
        for contact in raw_contacts.split(','):
            if not contact:
                continue
            mobility = self._ari.channels.getChannelVar(
                channelId=call_id, variable=f'PJSIP_CONTACT({contact},mobility)'
            )['value']
            if mobility == 'mobile':
                return True
        return False
