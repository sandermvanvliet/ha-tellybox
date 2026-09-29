"""Push coordinator: one event stream per Tellybox, every entity reads from it.

Contract only: subagent B implements the bodies. Signatures and behaviour are fixed; entities (subagent C)
use `data`, `client`, `control`, `last_watchers` and `async_command`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytellybox import AdminState, TellyboxClient


@dataclass
class TellyboxData:
    """`entry.runtime_data`."""

    client: TellyboxClient
    coordinator: TellyboxCoordinator


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

    def __init__(self, hass: HomeAssistant, entry: TellyboxConfigEntry, client: TellyboxClient) -> None:
        raise NotImplementedError

    @property
    def client(self) -> TellyboxClient:
        raise NotImplementedError

    @property
    def instance_id(self) -> str:
        """The config entry's unique id (the server's instance id)."""
        raise NotImplementedError

    @property
    def control(self) -> bool:
        """Options: override buttons and actions are enabled (CONF_CONTROL, default True)."""
        raise NotImplementedError

    @property
    def last_watchers(self) -> tuple[int, ...]:
        raise NotImplementedError

    async def async_start(self) -> None:
        raise NotImplementedError

    async def async_stop(self) -> None:
        raise NotImplementedError

    async def async_command(self, command: Callable[[], Awaitable[Any]]) -> Any:
        """Run a client call for an entity or action and turn client errors into HomeAssistantError with a
        translation key (`exceptions` in strings.json): forbidden (read-only token), time_up, unavailable,
        connection, request (with Tellybox's detail). A 401 also starts reauth. If the call returns an
        AdminState, it becomes the coordinator's data at once (no waiting for the event)."""
        raise NotImplementedError
