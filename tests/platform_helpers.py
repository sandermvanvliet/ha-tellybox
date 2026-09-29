"""Test-only harness: set up one entity platform against a minimal in-test coordinator.

Stands in for the real `TellyboxCoordinator` and `__init__.py` setup (same properties as the contract), so the
platform tests don't depend on them. One file, so it is easy to replace with `setup_integration` later.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytellybox import AdminState, TellyboxTimeUpError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tellybox.const import CONF_CONTROL, DOMAIN
from custom_components.tellybox.coordinator import TellyboxData

from .conftest import FakeTellyboxClient


class HarnessCoordinator(DataUpdateCoordinator[AdminState]):
    """A minimal coordinator with the contract's properties; `async_refresh` reads `client.state()`."""

    def __init__(self, hass: HomeAssistant, entry: MockConfigEntry, client: FakeTellyboxClient) -> None:
        super().__init__(hass, __import__("logging").getLogger(__name__), name=DOMAIN, config_entry=entry,
                         update_interval=None)
        self._client = client
        self._entry = entry
        self._last_watchers: tuple[int, ...] = ()

    async def _async_update_data(self) -> AdminState:
        state = await self._client.state()
        self._remember(state)
        return state

    def _remember(self, state: AdminState) -> None:
        if state.now_playing and state.now_playing.profile_ids:
            self._last_watchers = state.now_playing.profile_ids

    @property
    def client(self) -> FakeTellyboxClient:
        return self._client

    @property
    def instance_id(self) -> str:
        return self._entry.unique_id or ""

    @property
    def control(self) -> bool:
        return bool(self._entry.options.get(CONF_CONTROL, True))

    @property
    def last_watchers(self) -> tuple[int, ...]:
        return self._last_watchers

    async def async_command(self, command: Callable[[], Awaitable[Any]]) -> Any:
        try:
            result = await command()
        except TellyboxTimeUpError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="time_up") from err
        if isinstance(result, AdminState):
            self._remember(result)
            self.async_set_updated_data(result)
        return result

    async def push(self) -> None:
        """Take the fake's current state (what an event would deliver)."""
        await self.async_refresh()


async def setup_platform(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    fake_client: FakeTellyboxClient,
    platform: Platform,
    *,
    control: bool = True,
) -> HarnessCoordinator:
    """Add `entry`, give it runtime data around the fake, and set up one platform. Returns the coordinator."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_CONTROL: control})
    coordinator = HarnessCoordinator(hass, entry, fake_client)
    await coordinator.async_refresh()
    entry.runtime_data = TellyboxData(client=fake_client, coordinator=coordinator)  # type: ignore[arg-type]
    entry.mock_state(hass, ConfigEntryState.LOADED)
    await hass.config_entries.async_forward_entry_setups(entry, [platform])
    await hass.async_block_till_done()
    return coordinator


def uid(key: str, profile_id: int | None = None) -> str:
    """The unique id of an entity (see `entity.py`)."""
    from .conftest import INSTANCE_ID

    return f"{INSTANCE_ID}_{key}" if profile_id is None else f"{INSTANCE_ID}_profile_{profile_id}_{key}"


def entity_id(hass: HomeAssistant, domain: str, key: str, profile_id: int | None = None) -> str:
    from homeassistant.helpers import entity_registry as er

    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, uid(key, profile_id))
    assert found, f"no {domain} entity for {uid(key, profile_id)}"
    return found
