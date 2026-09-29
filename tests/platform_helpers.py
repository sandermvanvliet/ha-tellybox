"""Platform-test helpers: set up the real integration against the fake client, and entity lookups.

States reach entities the way they do in production: `fake_client.push()` puts the state on the fake event
stream, the coordinator's stream task applies it.
"""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tellybox.const import CONF_CONTROL, DOMAIN
from custom_components.tellybox.coordinator import TellyboxCoordinator

from .conftest import INSTANCE_ID, FakeTellyboxClient


async def setup_platform(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    fake_client: FakeTellyboxClient,
    platform: Platform | None = None,  # every platform is set up; kept for readability at call sites
    *,
    control: bool = True,
) -> TellyboxCoordinator:
    """Add `entry` with the control option, set up the integration with `fake_client`, return the coordinator."""
    patches = [
        patch("custom_components.tellybox.TellyboxClient", return_value=fake_client),
        patch("custom_components.tellybox.config_flow.TellyboxClient", return_value=fake_client),
    ]
    for p in patches:
        p.start()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, lambda _e: [p.stop() for p in reversed(patches)])
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_CONTROL: control})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data.coordinator


async def push_state(hass: HomeAssistant, fake_client: FakeTellyboxClient) -> None:
    """Deliver the fake's current state as an event and let entities update."""
    fake_client.push()
    await hass.async_block_till_done()


def uid(key: str, profile_id: int | None = None) -> str:
    """The unique id of an entity (see `entity.py`)."""
    return f"{INSTANCE_ID}_{key}" if profile_id is None else f"{INSTANCE_ID}_profile_{profile_id}_{key}"


def entity_id(hass: HomeAssistant, domain: str, key: str, profile_id: int | None = None) -> str:
    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, uid(key, profile_id))
    assert found, f"no {domain} entity for {uid(key, profile_id)}"
    return found
