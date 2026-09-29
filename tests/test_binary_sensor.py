"""Binary sensor platform tests."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory, Platform
from homeassistant.helpers import entity_registry as er

from custom_components.tellybox.const import DOMAIN

from .platform_helpers import entity_id, setup_platform, uid


async def _setup(hass, config_entry, fake_client):
    return await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)


def _on(hass, key, profile_id=None) -> str:
    return hass.states.get(entity_id(hass, "binary_sensor", key, profile_id)).state


async def test_states_from_fixture(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert _on(hass, "time_up") == "off"
    assert _on(hass, "last_five_minutes") == "off"
    assert _on(hass, "tv_reachable") == "on"
    # Mila is watching with time left; Noah is out of time
    assert _on(hass, "watching", 1) == "on"
    assert _on(hass, "watching", 2) == "off"
    assert _on(hass, "time_up", 1) == "off"
    assert _on(hass, "time_up", 2) == "on"
    assert _on(hass, "last_five_minutes", 1) == "off"
    assert _on(hass, "last_five_minutes", 2) == "on"
    for pid in (1, 2):
        assert _on(hass, "blocked", pid) == "off"
        assert _on(hass, "unlimited", pid) == "off"


async def test_updates(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    fake_client.set_state(
        group={**fake_client.state_data["group"], "time_up": True, "last_five": True},
        tv={**fake_client.state_data["tv"], "reachable": False, "connection": "unreachable"},
    )
    fake_client.set_profile(1, blocked=True, can_start=False, reason="blocked", watching=False)
    fake_client.set_profile(2, unlimited=True, remaining_s=None, can_start=True)
    await coordinator.push()
    await hass.async_block_till_done()
    assert _on(hass, "time_up") == "on"
    assert _on(hass, "last_five_minutes") == "on"
    assert _on(hass, "tv_reachable") == "off"
    assert _on(hass, "blocked", 1) == "on"
    assert _on(hass, "time_up", 1) == "on"
    assert _on(hass, "watching", 1) == "off"
    assert _on(hass, "unlimited", 2) == "on"
    assert _on(hass, "time_up", 2) == "off"


async def test_tv_reachable_class_and_category(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    entry = er.async_get(hass).async_get(entity_id(hass, "binary_sensor", "tv_reachable"))
    assert entry.original_device_class == BinarySensorDeviceClass.CONNECTIVITY
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.disabled_by is None


async def test_new_profile_adds_entities(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    reg = er.async_get(hass)
    assert reg.async_get_entity_id("binary_sensor", DOMAIN, uid("watching", 3)) is None
    fake_client.state_data["profiles"].append(
        {**fake_client.state_data["profiles"][1], "id": 3, "name": "Emma", "watching": True}
    )
    await coordinator.push()
    await hass.async_block_till_done()
    assert _on(hass, "watching", 3) == "on"
    for key in ("watching", "time_up", "last_five_minutes", "blocked", "unlimited"):
        assert reg.async_get_entity_id("binary_sensor", DOMAIN, uid(key, 3))


async def test_unique_ids(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    reg = er.async_get(hass)
    for key in ("time_up", "last_five_minutes", "tv_reachable"):
        assert reg.async_get_entity_id("binary_sensor", DOMAIN, uid(key))
    assert reg.async_get_entity_id("binary_sensor", DOMAIN, uid("time_up", 1))
    assert reg.async_get_entity_id("binary_sensor", DOMAIN, uid("tv_reachable", 1)) is None
