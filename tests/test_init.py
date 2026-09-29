"""Setup, unload, reload on options, and device cleanup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from pytellybox import TellyboxAuthError, TellyboxConnectionError

from custom_components.tellybox.const import CONF_CONTROL, profile_device_identifier

from .conftest import INSTANCE_ID
from .helpers import add_devices, core, no_platforms  # noqa: F401


async def test_setup_and_unload(hass, core, config_entry):
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.coordinator.data.instance_id == INSTANCE_ID
    assert core.stream_opens == 1
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_not_ready(hass, config_entry, patch_client, no_platforms):
    patch_client.fail_with = TellyboxConnectionError("down")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed_starts_reauth(hass, config_entry, patch_client, no_platforms):
    patch_client.fail_with = TellyboxAuthError("no")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_options_change_reloads(hass, core, config_entry):
    first = config_entry.runtime_data.coordinator
    hass.config_entries.async_update_entry(config_entry, options={CONF_CONTROL: False})
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.coordinator is not first
    assert config_entry.runtime_data.coordinator.control is False


async def test_gone_kid_device_is_removed(hass, core, config_entry):
    ids = add_devices(hass, config_entry, 1, 2)
    registry = dr.async_get(hass)
    core.state_data["profiles"] = [p for p in core.state_data["profiles"] if p["id"] != 2]
    core.push()
    await hass.async_block_till_done()
    assert registry.async_get(ids[2]) is None
    assert registry.async_get(ids[1]) is not None
    assert registry.async_get(ids["main"]) is not None


async def test_gone_kid_device_removed_on_setup(hass, config_entry, patch_client, no_platforms):
    config_entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    dev = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={profile_device_identifier(INSTANCE_ID, 9)}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert registry.async_get(dev.id) is None
