"""add_time_notification.yaml through the Home Assistant harness.

The notification goes through the real mobile_app `notify` device action (a mobile_app config entry is set
up); the device action ends in `notify.<mobile_app_...>`, which is what `async_mock_service` captures.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr, template
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)


from .blueprint_helpers import add_phone, automation_from_blueprint, notified, settle  # noqa: F401
from .platform_helpers import entity_id, setup_platform

FILE = "add_time_notification.yaml"


def tap(hass, action_id):
    hass.bus.async_fire("mobile_app_notification_action", {"action": action_id})


def kid_device_id(hass, profile_id):
    d = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{INSTANCE_ID}_profile_{profile_id}")})
    assert d
    return d.id


async def test_trigger_notifies_once_with_action_id_and_tag(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)
    phone = await add_phone(hass)
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": sensor, "notify_device": phone})

    fake_client.set_profile(1, last_five=True)
    await settle()

    assert len(notified) == 1
    data = notified[0]
    assert data["device_id"] == phone
    assert data["title"] == "Tellybox"
    assert data["message"] == "Mila's time is almost up. Add 15 minutes?"
    assert data["data"]["tag"] == f"tellybox_add_time_{sensor}"
    assert data["data"]["actions"] == [{"action": f"TELLYBOX_ADD_15_{sensor}", "title": "Add 15 minutes"}]
    assert fake_client.calls.count(("add_time", 15)) == 0  # nothing is added until the tap


async def test_tap_adds_time_for_the_kid_and_clears_the_notification(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)
    phone = await add_phone(hass)
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": sensor, "notify_device": phone, "minutes": 20})
    extra_before = next(p for p in fake_client.state_data["profiles"] if p["id"] == 1)["extra_s"] or 0
    other_before = next(p for p in fake_client.state_data["profiles"] if p["id"] != 1)["extra_s"] or 0

    fake_client.set_profile(1, last_five=True)
    await settle()
    tap(hass, f"TELLYBOX_ADD_20_{sensor}")
    await settle()

    assert ("add_time", 20) in fake_client.calls
    profiles = {p["id"]: p for p in fake_client.state_data["profiles"]}
    assert (profiles[1]["extra_s"] or 0) == extra_before + 20 * 60
    assert all((p["extra_s"] or 0) == other_before for i, p in profiles.items() if i != 1)  # only Mila
    assert len(notified) == 2
    assert notified[1]["message"] == "clear_notification"
    assert notified[1]["data"] == {"tag": f"tellybox_add_time_{sensor}"}


async def test_different_action_id_is_ignored(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)
    phone = await add_phone(hass)
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": sensor, "notify_device": phone})

    fake_client.set_profile(1, last_five=True)
    await settle()
    tap(hass, "TELLYBOX_ADD_15_binary_sensor.someone_else")
    tap(hass, "SOMETHING_ELSE")
    await settle()

    assert not [c for c in fake_client.calls if c[0] == "add_time"]
    assert len(notified) == 1  # no clear either


async def test_timeout_without_tap_adds_nothing(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)
    phone = await add_phone(hass)
    await automation_from_blueprint(
        hass, FILE, {"trigger_sensor": sensor, "notify_device": phone, "answer_timeout_minutes": 5}
    )

    fake_client.set_profile(1, last_five=True)
    await settle()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await settle()
    tap(hass, f"TELLYBOX_ADD_15_{sensor}")  # too late, the run has ended
    await settle()

    assert not [c for c in fake_client.calls if c[0] == "add_time"]
    assert len(notified) == 1


async def test_tellybox_device_sensor_adds_time_for_everyone(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes")
    phone = await add_phone(hass)
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": sensor, "notify_device": phone})
    adds: list = []
    original = fake_client.add_time

    async def spy(minutes, profile_ids=None):
        adds.append((minutes, profile_ids))
        return await original(minutes, profile_ids)

    fake_client.add_time = spy

    fake_client.set_state(group={**fake_client.state_data["group"], "last_five": True})
    await settle()
    assert "Tellybox's time is almost up" in notified[0]["message"]
    tap(hass, f"TELLYBOX_ADD_15_{sensor}")
    await settle()

    assert adds == [(15, None)]


async def test_unlimited_kid_gets_no_notification(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)
    assert hass.states.get(entity_id(hass, "binary_sensor", "unlimited", 1)).state == "off"
    phone = await add_phone(hass)
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": sensor, "notify_device": phone})

    fake_client.set_profile(1, unlimited=True)
    await settle()
    assert hass.states.get(entity_id(hass, "binary_sensor", "unlimited", 1)).state == "on"
    fake_client.set_profile(1, last_five=True)
    await settle()

    assert notified == []


async def test_unavailable_to_on_does_not_notify(hass, config_entry, fake_client, notified):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    phone = await add_phone(hass)
    hass.states.async_set("binary_sensor.plain", "unavailable")
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": "binary_sensor.plain", "notify_device": phone})

    hass.states.async_set("binary_sensor.plain", "on")
    await settle()

    assert notified == []


async def test_control_off_fails_visibly_and_adds_nothing(hass, config_entry, fake_client, notified, caplog):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR, control=False)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)
    phone = await add_phone(hass)
    await automation_from_blueprint(hass, FILE, {"trigger_sensor": sensor, "notify_device": phone})

    fake_client.set_profile(1, last_five=True)
    await settle()
    tap(hass, f"TELLYBOX_ADD_15_{sensor}")
    await settle()

    assert not [c for c in fake_client.calls if c[0] == "add_time"]
    assert "Blueprint test 0" in caplog.text and "Error" in caplog.text
