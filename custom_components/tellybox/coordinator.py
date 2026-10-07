"""Push coordinator: one event stream per Tellybox, every entity reads from it."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytellybox import (
    AdminState,
    ServerEvent,
    TellyboxAuthError,
    TellyboxClient,
    TellyboxConnectionError,
    TellyboxError,
    TellyboxForbiddenError,
    TellyboxTimeUpError,
    TellyboxUnavailableError,
)

from .const import (
    CAPABILITY_TYPED_EVENTS,
    CONF_CONTROL,
    DOMAIN,
    RECONNECT_MAX_S,
    RECONNECT_MIN_S,
    UNAVAILABLE_AFTER_S,
    main_device_identifier,
    profile_device_identifier,
)
from .events import (
    EVENT_NAME,
    EVENT_TV_REACHABLE,
    EVENT_TV_UNREACHABLE,
    TellyboxEvent,
    build_payload,
    diff_states,
    from_server_event,
)

if TYPE_CHECKING:
    from .history_coordinator import TellyboxHistoryCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class TellyboxData:
    """`entry.runtime_data`."""

    client: TellyboxClient
    coordinator: TellyboxCoordinator
    history: TellyboxHistoryCoordinator | None = None  # only when Tellybox advertises the history capability


type TellyboxConfigEntry = ConfigEntry[TellyboxData]


class TellyboxCoordinator(DataUpdateCoordinator[AdminState]):
    """No polling (`update_interval=None`).

    - The first refresh (`async_config_entry_first_refresh`) calls `client.state()`: a 401 raises
      ConfigEntryAuthFailed (reauth), a connection problem ConfigEntryNotReady.
    - `async_start()` then runs a background task (`entry.async_create_background_task`) reading
      `client.events()` and calling `async_set_updated_data` for each state.
    - When the stream breaks it reconnects with backoff from RECONNECT_MIN_S doubling to RECONNECT_MAX_S,
      resetting after a successful event. Entities stay available with the last data until the stream has been
      down for UNAVAILABLE_AFTER_S; then `last_update_success` becomes False and listeners are told.
    - A 401 at any point starts reauth (`entry.async_start_reauth`) and stops the task.
    - `async_stop()` cancels the task (on unload).
    - `last_watchers` remembers the most recent non-empty `now_playing.profile_ids`, for playing from Home
      Assistant without choosing kids.
    """

    config_entry: TellyboxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TellyboxConfigEntry, client: TellyboxClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None)
        self._client = client
        self._last_watchers: tuple[int, ...] = ()
        self._task: asyncio.Task[None] | None = None
        self._unavailable_timer: CALLBACK_TYPE | None = None
        self._last_state: AdminState | None = None  # the baseline events are diffed against; survives reconnects
        self._closing = False  # set by async_stop: no events while unloading
        # Per connection (set in `_run_stream`): True when Tellybox sends typed events. Then the state diff only
        # derives the TV reachability events (the typed catalog has none); everything else comes from the server,
        # so no event fires twice. False (older Tellybox): the diff derives every event, as before.
        self._typed = False

    @property
    def client(self) -> TellyboxClient:
        return self._client

    @property
    def instance_id(self) -> str:
        """The config entry's unique id (the server's instance id)."""
        assert self.config_entry.unique_id is not None
        return self.config_entry.unique_id

    @property
    def control(self) -> bool:
        """Options: override buttons and actions are enabled (CONF_CONTROL, default True)."""
        return bool(self.config_entry.options.get(CONF_CONTROL, True))

    @property
    def last_watchers(self) -> tuple[int, ...]:
        return self._last_watchers

    # -- data

    async def _async_update_data(self) -> AdminState:
        try:
            state = await self._client.state()
        except TellyboxAuthError as err:
            raise ConfigEntryAuthFailed from err
        except TellyboxError as err:
            raise ConfigEntryNotReady(f"Can't get Tellybox's state: {err}") from err
        self._remember(state)
        self._last_state = state  # baseline: no events
        return state

    def _remember(self, state: AdminState) -> None:
        if state.now_playing and state.now_playing.profile_ids:
            self._last_watchers = tuple(state.now_playing.profile_ids)

    @callback
    def _apply(self, state: AdminState) -> None:
        self._remember(state)
        self._cancel_unavailable_timer()
        self.last_update_success = True
        self.async_set_updated_data(state)
        old, self._last_state = self._last_state, state
        if old is not None and not self._closing:
            self._fire_events(old, state)

    def _find_device(self, registry: dr.DeviceRegistry, identifier: tuple[str, str]) -> dr.DeviceEntry | None:
        # `async_get_device` is deprecated on recent Home Assistant (identifiers are per config entry now);
        # fall back to it on versions that predate `async_get_device_by_identifier`.
        by_identifier = getattr(registry, "async_get_device_by_identifier", None)
        if by_identifier is not None:
            return by_identifier(identifier, self.config_entry.entry_id)
        return registry.async_get_device(identifiers={identifier})

    def _fire_events(self, old: AdminState, new: AdminState) -> None:
        """Fire a `tellybox_event` per transition from `old` to `new`; never raises. In typed mode only the TV
        reachability transitions are fired: the server sends the rest."""
        try:
            events = diff_states(old, new)
            if self._typed:
                events = [e for e in events if e.type in (EVENT_TV_UNREACHABLE, EVENT_TV_REACHABLE)]
            self._fire(events, {p.id: p.name for p in new.profiles})
        except Exception:  # noqa: BLE001 - a bad diff must never break the stream
            _LOGGER.exception("Failed to derive Tellybox events")

    @callback
    def _handle_server_event(self, event: ServerEvent) -> None:
        """Fire the bus events for one typed server event; never raises."""
        if self._closing:
            return
        try:
            state = self._last_state if self._last_state is not None else self.data
            names = {p.id: p.name for p in state.profiles} if state is not None else {}
            self._fire(from_server_event(event), names)
        except Exception:  # noqa: BLE001 - a bad event must never break the stream
            _LOGGER.exception("Failed to handle Tellybox event")

    def _fire(self, events: list[TellyboxEvent], names: dict[int, str]) -> None:
        """Resolve each event's device and fire it on the bus. A kid unknown to the registry is skipped."""
        registry = dr.async_get(self.hass)
        for event in events:
            if event.profile_id is not None and event.profile_id not in names:
                _LOGGER.debug("Skipping %s event: unknown kid", event.type)
                continue
            identifier = (
                main_device_identifier(self.instance_id)
                if event.profile_id is None
                else profile_device_identifier(self.instance_id, event.profile_id)
            )
            device = self._find_device(registry, identifier)
            if device is None:
                _LOGGER.debug("Skipping %s event: device not registered yet", event.type)
                continue
            payload = build_payload(
                event,
                instance_id=self.instance_id,
                device_id=device.id,
                profile_name=names.get(event.profile_id),
            )
            self.hass.bus.async_fire(EVENT_NAME, payload)

    # -- event stream

    async def async_start(self) -> None:
        """Start the background event-stream task (once)."""
        if self._task is not None and not self._task.done():
            return
        self._task = self.config_entry.async_create_background_task(
            self.hass, self._run_stream(), name=f"{DOMAIN} event stream"
        )

    async def async_stop(self) -> None:
        self._closing = True
        self._cancel_unavailable_timer()
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def _cancel_unavailable_timer(self) -> None:
        if self._unavailable_timer is not None:
            self._unavailable_timer()
            self._unavailable_timer = None

    @callback
    def _mark_unavailable(self, _now: datetime) -> None:
        self._unavailable_timer = None
        self.last_update_success = False
        self.async_update_listeners()

    async def _run_stream(self) -> None:
        backoff = RECONNECT_MIN_S
        while True:
            try:
                # Read the capabilities before every connect, so a Tellybox upgrade is picked up on reconnect.
                self._typed = await self._typed_events_supported()
                source = self._client.stream(typed=True) if self._typed else self._client.events()
                async for item in source:
                    backoff = RECONNECT_MIN_S
                    if isinstance(item, ServerEvent):
                        self._handle_server_event(item)
                    else:
                        self._apply(item)
                _LOGGER.debug("Tellybox event stream ended")
            except TellyboxAuthError:
                self._start_reauth()
                return
            except (TellyboxError, OSError, TimeoutError) as err:
                _LOGGER.debug("Tellybox event stream failed: %s", type(err).__name__)
            if self._unavailable_timer is None and self.last_update_success:
                self._unavailable_timer = async_call_later(self.hass, UNAVAILABLE_AFTER_S, self._mark_unavailable)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX_S)

    async def _typed_events_supported(self) -> bool:
        """Does Tellybox advertise typed events? A failing `info()` counts as no (a 401 still raises)."""
        try:
            info = await self._client.info()
        except TellyboxAuthError:
            raise
        except (TellyboxError, OSError, TimeoutError) as err:
            _LOGGER.debug("Can't read Tellybox's capabilities, using state-derived events: %s", err)
            return False
        return bool(info.supports(CAPABILITY_TYPED_EVENTS))

    def _start_reauth(self) -> None:
        self._cancel_unavailable_timer()
        self.config_entry.async_start_reauth(self.hass)

    # -- commands

    async def async_command(self, command: Callable[[], Awaitable[Any]]) -> Any:
        """Run a client call for an entity or action and turn client errors into HomeAssistantError with a
        translation key (`exceptions` in strings.json): forbidden (read-only token), time_up, unavailable,
        connection, request (with Tellybox's detail). A 401 also starts reauth. If the call returns an
        AdminState, it becomes the coordinator's data at once (no waiting for the event)."""
        try:
            result = await command()
        except TellyboxAuthError as err:
            self._start_reauth()
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="auth") from err
        except TellyboxForbiddenError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="forbidden") from err
        except TellyboxTimeUpError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="time_up") from err
        except TellyboxUnavailableError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="unavailable") from err
        except TellyboxConnectionError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="connection") from err
        except TellyboxError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request", translation_placeholders={"detail": str(err)}
            ) from err
        if isinstance(result, AdminState):
            self._apply(result)
        return result
