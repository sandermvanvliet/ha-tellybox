"""Button platform tests."""

from __future__ import annotations

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.helpers import entity_registry as er

from custom_components.tellybox.const import DOMAIN

from .platform_helpers import entity_id, push_state, setup_platform, uid

TELLYBOX_KEYS = ("stop_now", "add_15_minutes", "add_30_minutes", "unlimited_today", "block_today", "clear_overrides")
KID_KEYS = TELLYBOX_KEYS[1:]


async def _setup(hass, config_entry, fake_client, control=True):
    return await setup_platform(hass, config_entry, fake_client, Platform.BUTTON, control=control)


async def _press(hass, key, profile_id=None):
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id(hass, "button", key, profile_id)}, blocking=True
    )


async def test_buttons_exist_and_are_hidden(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    reg = er.async_get(hass)
    for key in TELLYBOX_KEYS:
        entry = reg.async_get(entity_id(hass, "button", key))
        assert entry.hidden_by == er.RegistryEntryHider.INTEGRATION
        assert entry.disabled_by is None
    for pid in (1, 2):
        for key in KID_KEYS:
            entry = reg.async_get(entity_id(hass, "button", key, pid))
            assert entry.hidden_by == er.RegistryEntryHider.INTEGRATION
        assert reg.async_get_entity_id("button", DOMAIN, uid("stop_now", pid)) is None


async def test_no_buttons_without_control(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, control=False)
    assert not hass.states.async_entity_ids("button")
    assert not [e for e in er.async_get(hass).entities.values() if e.domain == "button"]


@pytest.mark.parametrize(
    ("key", "call"),
    [
        ("add_15_minutes", ("add_time", 15)),
        ("add_30_minutes", ("add_time", 30)),
        ("unlimited_today", ("set_unlimited", None)),
        ("block_today", ("block", None)),
        ("clear_overrides", ("clear_today", None)),
        ("stop_now", ("stop_now",)),
    ],
)
async def test_tellybox_buttons_target_everyone(hass, config_entry, fake_client, key, call):
    await _setup(hass, config_entry, fake_client)
    await _press(hass, key)
    assert call in fake_client.calls
    if key == "stop_now":
        assert fake_client.state_data["now_playing"] is None
    else:
        # everyone: profile_ids is None (the fake records the resolved list as None)
        assert fake_client.calls[-1][1] is None


@pytest.mark.parametrize(
    ("key", "name"),
    [
        ("add_15_minutes", "add_time_targets"),
        ("add_30_minutes", "add_time_targets"),
        ("unlimited_today", "set_unlimited"),
        ("block_today", "block"),
        ("clear_overrides", "clear_today"),
    ],
)
async def test_kid_buttons_target_that_kid(hass, config_entry, fake_client, key, name):
    await _setup(hass, config_entry, fake_client)
    await _press(hass, key, 2)
    assert (name, [2]) in fake_client.calls


async def test_kid_button_changes_state_at_once(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    await _press(hass, "add_15_minutes", 1)
    assert coordinator.data.profile(1).extra_s == 1800
    assert coordinator.data.profile(2).extra_s == 0


async def test_new_profile_gets_buttons(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    fake_client.state_data["profiles"].append({**fake_client.state_data["profiles"][1], "id": 3, "name": "Emma"})
    await push_state(hass, fake_client)
    await hass.async_block_till_done()
    await _press(hass, "block_today", 3)
    assert ("block", [3]) in fake_client.calls

