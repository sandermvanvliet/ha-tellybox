"""Sensor platform tests."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
import pytest
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.tellybox.const import DOMAIN, main_device_identifier, profile_device_identifier

from .conftest import INSTANCE_ID
from .platform_helpers import entity_id, push_state, setup_platform, uid


async def _setup(hass, config_entry, fake_client):
    return await setup_platform(hass, config_entry, fake_client, Platform.SENSOR)


def _state(hass, key, profile_id=None):
    return hass.states.get(entity_id(hass, "sensor", key, profile_id))


async def test_tellybox_sensor_states(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert _state(hass, "now_playing_show").state == "Harbour Pups"
    assert _state(hass, "now_playing_show").attributes["show_id"] == 2
    assert _state(hass, "now_playing_show").attributes["episode_id"] == 4
    assert _state(hass, "now_playing_episode").state == "Alongside"
    assert float(_state(hass, "time_left").state) == pytest.approx(1790 / 60)  # suggested unit: minutes
    assert _state(hass, "downloads_awaiting_approval").state == "3"
    queue = _state(hass, "download_queue")
    assert queue.state == "2"
    assert queue.attributes["failed"] == 0


async def test_kid_sensor_states(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert float(_state(hass, "time_left", 1).state) == pytest.approx(1790 / 60)
    assert float(_state(hass, "time_left", 2).state) == 0
    assert float(_state(hass, "time_used_today", 1).state) == pytest.approx(2710 / 60)
    assert float(_state(hass, "allowance_today", 1).state) == pytest.approx(4500 / 60)
    assert float(_state(hass, "allowance_today", 2).state) == pytest.approx(2700 / 60)
    assert float(_state(hass, "session_time", 1).state) == 20
    assert _state(hass, "session_time", 2).state == "unknown"


async def test_units_and_classes(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    reg = er.async_get(hass)
    for key, pid in (("time_left", None), ("time_left", 1), ("time_used_today", 1), ("session_time", 1)):
        entry = reg.async_get(entity_id(hass, "sensor", key, pid))
        assert entry.device_class is None and entry.original_device_class == SensorDeviceClass.DURATION
        assert entry.unit_of_measurement == "min"
        assert entry.capabilities["state_class"] in (SensorStateClass.MEASUREMENT, SensorStateClass.TOTAL_INCREASING)
    used = reg.async_get(entity_id(hass, "sensor", "time_used_today", 1))
    assert used.capabilities["state_class"] == SensorStateClass.TOTAL_INCREASING
    assert _state(hass, "time_left").attributes["unit_of_measurement"] == "min"
    allowance = reg.async_get(entity_id(hass, "sensor", "allowance_today", 1))
    assert allowance.entity_category == er.EntityCategory.DIAGNOSTIC


async def test_media_disk_use_disabled_diagnostic(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    reg = er.async_get(hass)
    entry = reg.async_get(entity_id(hass, "sensor", "media_disk_use"))
    assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC
    assert entry.original_device_class == SensorDeviceClass.DATA_SIZE
    assert entry.unit_of_measurement == "GB"
    assert hass.states.get(entry.entity_id) is None


async def test_unlimited_and_idle_are_unknown(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    fake_client.set_profile(1, unlimited=True, remaining_s=None)
    fake_client.set_state(now_playing=None, group={**fake_client.state_data["group"], "remaining_s": None})
    await push_state(hass, fake_client)
    await hass.async_block_till_done()
    assert _state(hass, "time_left", 1).state == "unknown"
    assert _state(hass, "time_left").state == "unknown"
    assert _state(hass, "now_playing_show").state == "unknown"
    assert _state(hass, "now_playing_episode").state == "unknown"


async def test_update_from_pushed_state(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    fake_client.set_profile(1, remaining_s=600, used_s=3900)
    fake_client.set_state(jobs={"queued": 0, "running": 0, "failed": 2, "held_ready": 0})
    await push_state(hass, fake_client)
    await hass.async_block_till_done()
    assert float(_state(hass, "time_left", 1).state) == 10
    assert float(_state(hass, "time_used_today", 1).state) == 65
    assert _state(hass, "download_queue").state == "0"
    assert _state(hass, "download_queue").attributes["failed"] == 2
    assert _state(hass, "downloads_awaiting_approval").state == "0"


async def test_new_profile_adds_device_and_entities(hass, config_entry, fake_client):
    coordinator = await _setup(hass, config_entry, fake_client)
    assert er.async_get(hass).async_get_entity_id("sensor", DOMAIN, uid("time_left", 3)) is None
    fake_client.state_data["profiles"].append(
        {**fake_client.state_data["profiles"][1], "id": 3, "name": "Emma", "remaining_s": 900}
    )
    fake_client.push()
    await push_state(hass, fake_client)
    await hass.async_block_till_done()
    assert float(_state(hass, "time_left", 3).state) == 15
    device = dr.async_get(hass).async_get_device_by_identifier(profile_device_identifier(INSTANCE_ID, 3), config_entry.entry_id)
    assert device and device.name == "Emma"


async def test_unique_ids_and_device_layout(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    reg = er.async_get(hass)
    devices = dr.async_get(hass)
    assert reg.async_get_entity_id("sensor", DOMAIN, f"{INSTANCE_ID}_time_left")
    assert reg.async_get_entity_id("sensor", DOMAIN, f"{INSTANCE_ID}_profile_1_time_left")
    main = devices.async_get_device_by_identifier(main_device_identifier(INSTANCE_ID), config_entry.entry_id)
    mila = devices.async_get_device_by_identifier(profile_device_identifier(INSTANCE_ID, 1), config_entry.entry_id)
    assert main and mila and mila.via_device_id == main.id
    assert reg.async_get(entity_id(hass, "sensor", "time_left")).device_id == main.id
    assert reg.async_get(entity_id(hass, "sensor", "time_left", 1)).device_id == mila.id
    assert reg.async_get(entity_id(hass, "sensor", "time_left", 1)).has_entity_name


async def test_kid_entities_go_with_a_deleted_profile(hass, config_entry, fake_client):
    """A kid deleted in Tellybox loses its device and entities (cleanup in __init__.py)."""
    await _setup(hass, config_entry, fake_client)
    time_left_2 = entity_id(hass, "sensor", "time_left", 2)
    fake_client.state_data["profiles"] = [p for p in fake_client.state_data["profiles"] if p["id"] != 2]
    await push_state(hass, fake_client)
    assert er.async_get(hass).async_get(time_left_2) is None
    assert _state(hass, "time_left", 1).state != "unavailable"
