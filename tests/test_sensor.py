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


async def test_inbox_sensors(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert _state(hass, "inbox_pending").state == "4"
    assert _state(hass, "inbox_unhealthy").state == "0"
    latest = _state(hass, "inbox_latest_received")
    assert latest.state == "2026-09-29T11:42:00+00:00"
    assert latest.attributes["device_class"] == "timestamp"


async def test_inbox_updates_on_a_new_upload(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    fake_client.set_state(inbox={"pending": 5, "unhealthy": 1, "latest_received_at": "2026-09-29T12:00:00+00:00"})
    await push_state(hass, fake_client)
    assert _state(hass, "inbox_pending").state == "5"
    assert _state(hass, "inbox_unhealthy").state == "1"
    assert _state(hass, "inbox_latest_received").state == "2026-09-29T12:00:00+00:00"


async def test_inbox_empty_has_no_latest_upload(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    fake_client.set_state(inbox={"pending": 0, "unhealthy": 0, "latest_received_at": None})
    await push_state(hass, fake_client)
    assert _state(hass, "inbox_pending").state == "0"
    assert _state(hass, "inbox_latest_received").state == "unknown"


async def test_sessions_and_watching_on(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    sessions = _state(hass, "active_sessions")
    assert sessions.state == "1"
    assert sessions.attributes["sessions"] == [
        {"target": "tv", "label": "TV", "state": "playing", "show_id": 2, "episode_id": 4, "profile_ids": [1]}
    ]
    assert _state(hass, "watching_on", 1).state == "TV"
    assert _state(hass, "watching_on", 2).state == "unknown"
    assert _state(hass, "watching_on", 1).attributes["target"] == "tv"
    assert _state(hass, "watching_on", 1).attributes["state"] == "playing"
    assert _state(hass, "watching_on", 2).attributes["target"] is None
    assert _state(hass, "watching_on", 2).attributes["state"] is None
    fake_client.set_state(sessions=[
        {"key": "device:abc", "target": "device", "label": "iPhone Safari", "device_id": "abc", "episode_id": 5,
         "show_id": 2, "title": "Lost Ball", "state": "paused", "position_s": 10, "duration_s": 600,
         "profile_ids": [2]},
    ])
    await push_state(hass, fake_client)
    assert _state(hass, "active_sessions").state == "1"
    assert _state(hass, "watching_on", 1).state == "unknown"
    assert _state(hass, "watching_on", 2).state == "iPhone Safari"
    assert _state(hass, "watching_on", 2).attributes["target"] == "device"
    assert _state(hass, "watching_on", 2).attributes["state"] == "paused"
    assert _state(hass, "watching_on", 1).attributes["target"] is None
    assert _state(hass, "watching_on", 1).attributes["state"] is None
    fake_client.set_state(sessions=[])
    await push_state(hass, fake_client)
    assert _state(hass, "active_sessions").state == "0"


async def test_group_reason_action_and_reset(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert _state(hass, "time_up_reason").state == "unknown"
    assert _state(hass, "playback_action").state == "continue"
    assert _state(hass, "next_reset").state == "2026-09-30T02:00:00+00:00"
    fake_client.set_state(group={**fake_client.state_data["group"], "reason": "session_max",
                                 "action": "finish_then_stop"})
    await push_state(hass, fake_client)
    assert _state(hass, "time_up_reason").state == "session_max"
    assert _state(hass, "playback_action").state == "finish_then_stop"
    reg = er.async_get(hass)
    assert reg.async_get(entity_id(hass, "sensor", "next_reset")).entity_category == er.EntityCategory.DIAGNOSTIC


async def test_visible_shows_and_sources(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert _state(hass, "visible_shows", 1).state == "2"
    assert _state(hass, "visible_shows", 2).state == "1"
    assert _state(hass, "allowance_source", 1).state == "inherit"
    assert _state(hass, "max_session_source", 1).state == "custom"
    assert float(_state(hass, "max_session", 1).state) == 90
    assert _state(hass, "max_session", 2).state == "unknown"  # no maximum
    fake_client.set_profile(2, visible_shows=0)
    await push_state(hass, fake_client)
    assert _state(hass, "visible_shows", 2).state == "0"


async def test_unlimited_allowance_profile(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    fake_client.set_profile(1, allowance_s=None, allowance_source="unlimited", remaining_s=None, unlimited=False)
    await push_state(hass, fake_client)
    assert _state(hass, "allowance_today", 1).state == "unknown"
    assert _state(hass, "allowance_source", 1).state == "unlimited"
    assert _state(hass, "time_left", 1).state == "unknown"


async def test_ui_mode_disabled_diagnostic_enum(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    entry = er.async_get(hass).async_get(entity_id(hass, "sensor", "ui_mode", 1))
    assert entry.unique_id == uid("ui_mode", 1)
    assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC
    assert entry.original_device_class == SensorDeviceClass.ENUM
    assert entry.capabilities["options"] == ["icons", "text"]
    assert hass.states.get(entry.entity_id) is None


async def test_ui_mode_states_update_and_unknown(hass, config_entry, fake_client):
    reg = er.async_get(hass)
    config_entry.add_to_hass(hass)
    for pid in (1, 2):  # enable the disabled-by-default entities up front
        reg.async_get_or_create("sensor", DOMAIN, uid("ui_mode", pid), config_entry=config_entry, disabled_by=None)
    await _setup(hass, config_entry, fake_client)
    assert _state(hass, "ui_mode", 1).state == "icons"
    assert _state(hass, "ui_mode", 2).state == "text"
    fake_client.set_profile(1, ui_mode="text")
    await push_state(hass, fake_client)
    assert _state(hass, "ui_mode", 1).state == "text"
    fake_client.set_profile(2, ui_mode=None)  # an older Tellybox
    await push_state(hass, fake_client)
    assert _state(hass, "ui_mode", 2).state == "unknown"
