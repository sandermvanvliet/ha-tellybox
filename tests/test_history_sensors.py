"""The per-kid history sensors (HA-12)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytellybox import TellyboxConnectionError
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.tellybox.const import CAPABILITY_HISTORY, DOMAIN, HISTORY_POLL_S, profile_device_identifier

from .conftest import INSTANCE_ID
from .platform_helpers import entity_id, push_state, setup_platform, uid

KEYS = ("time_used_yesterday", "time_used_7d_average", "last_watched")


def _state(hass, key, profile_id):
    return hass.states.get(entity_id(hass, "sensor", key, profile_id))


async def _refresh(hass, fake_client):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HISTORY_POLL_S + 5))
    await hass.async_block_till_done()


async def test_values_from_the_history(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    assert float(_state(hass, "time_used_yesterday", 1).state) == 60  # minutes
    assert float(_state(hass, "time_used_yesterday", 2).state) == 30
    # Mila: days 1..7 = 3600, 0, 1800, 2400, 3000, 600, 1200 = 12600 / 7 = 1800 s
    assert float(_state(hass, "time_used_7d_average", 1).state) == 30
    # Noah: 1800, 1800, 0, 900, 0, 2700, 0 = 7200 / 7 = 1028.57 -> 1029 s
    assert float(_state(hass, "time_used_7d_average", 2).state) == pytest.approx(1029 / 60)


async def test_no_entities_without_the_capability(hass, config_entry, fake_client):
    fake_client.capabilities = tuple(c for c in fake_client.capabilities if c != CAPABILITY_HISTORY)
    await setup_platform(hass, config_entry, fake_client)
    registry = er.async_get(hass)
    for key in KEYS:
        for pid in (1, 2):
            assert registry.async_get_entity_id("sensor", DOMAIN, uid(key, pid)) is None


async def test_units_classes_unique_ids_and_devices(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    registry = er.async_get(hass)
    for key in ("time_used_yesterday", "time_used_7d_average"):
        entry = registry.async_get(entity_id(hass, "sensor", key, 1))
        assert entry.unique_id == f"{INSTANCE_ID}_profile_1_{key}"
        assert entry.original_device_class == SensorDeviceClass.DURATION
        assert entry.unit_of_measurement == "min"
        assert entry.capabilities["state_class"] == SensorStateClass.MEASUREMENT
    last = registry.async_get(entity_id(hass, "sensor", "last_watched", 1))
    assert last.unique_id == f"{INSTANCE_ID}_profile_1_last_watched"
    assert last.original_device_class == SensorDeviceClass.TIMESTAMP
    device = dr.async_get(hass).async_get_device_by_identifier(
        profile_device_identifier(INSTANCE_ID, 2), config_entry.entry_id)
    on_device = {e.unique_id for e in er.async_entries_for_device(registry, device.id)}
    assert {uid(k, 2) for k in KEYS} <= on_device


async def test_last_watched_attributes(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    mila = _state(hass, "last_watched", 1)
    assert dt_util.parse_datetime(mila.state) == datetime(2026, 9, 29, 8, 20, tzinfo=timezone.utc)  # ended_at
    assert mila.attributes["episode_title"] == "Alongside"
    assert mila.attributes["show"] == "Harbour Pups"
    assert mila.attributes["target"] == "tv"
    noah = _state(hass, "last_watched", 2)
    assert noah.state == "unknown"
    assert "episode_title" not in noah.attributes


async def test_last_watched_open_session_uses_started_at(hass, config_entry, fake_client):
    fake_client.history_data["profiles"][0]["last_watched"]["ended_at"] = None
    await setup_platform(hass, config_entry, fake_client)
    state = _state(hass, "last_watched", 1)
    assert dt_util.parse_datetime(state.state) == datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)


async def test_missing_day_gives_none(hass, config_entry, fake_client):
    fake_client.history_data["profiles"][0]["days"] = fake_client.history_data["profiles"][0]["days"][:1]
    await setup_platform(hass, config_entry, fake_client)
    assert _state(hass, "time_used_yesterday", 1).state == "unknown"


async def test_average_with_fewer_than_seven_days(hass, config_entry, fake_client):
    fake_client.history_data["profiles"][0]["days"] = fake_client.history_data["profiles"][0]["days"][:4]
    await setup_platform(hass, config_entry, fake_client)
    # days 1..3 = 3600 + 0 + 1800 = 5400 / 7 = 771.43 -> 771 s: zeros for the days not returned
    assert float(_state(hass, "time_used_7d_average", 1).state) == pytest.approx(771 / 60)


async def test_kid_missing_from_the_history_is_unknown(hass, config_entry, fake_client):
    fake_client.history_data["profiles"] = [p for p in fake_client.history_data["profiles"] if p["id"] == 2]
    await setup_platform(hass, config_entry, fake_client)
    for key in KEYS:
        assert _state(hass, key, 1).state == "unknown"
    assert float(_state(hass, "time_used_yesterday", 2).state) == 30


async def test_profile_order_in_the_history_does_not_matter(hass, config_entry, fake_client):
    fake_client.history_data["profiles"].reverse()
    await setup_platform(hass, config_entry, fake_client)
    assert float(_state(hass, "time_used_yesterday", 1).state) == 60
    assert float(_state(hass, "time_used_yesterday", 2).state) == 30


async def test_unavailable_after_a_failed_update_and_back(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    fake_client.history_error = TellyboxConnectionError("down")
    await _refresh(hass, fake_client)
    for key in KEYS:
        assert _state(hass, key, 1).state == "unavailable"
    # the kid's other sensors are unaffected
    assert _state(hass, "time_used_today", 1).state != "unavailable"
    fake_client.history_error = None
    fake_client.history_data["profiles"][0]["days"][1]["used_s"] = 600
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2 * HISTORY_POLL_S + 30))
    await hass.async_block_till_done()
    assert float(_state(hass, "time_used_yesterday", 1).state) == 10


async def test_a_new_kid_gets_the_sensors(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    kid = {**fake_client.state_data["profiles"][1], "id": 3, "name": "Eva"}
    fake_client.state_data["profiles"].append(kid)
    fake_client.history_data["profiles"].append({"id": 3, "name": "Eva", "last_watched": None, "days": [
        {"date": "2026-09-29", "used_s": 0, "extra_s": 0, "unlimited": False, "blocked": False},
        {"date": "2026-09-28", "used_s": 420, "extra_s": 0, "unlimited": False, "blocked": False}]})
    await push_state(hass, fake_client)
    assert _state(hass, "time_used_yesterday", 3).state == "unknown"  # not in the history until the next update
    await _refresh(hass, fake_client)
    assert float(_state(hass, "time_used_yesterday", 3).state) == 7
