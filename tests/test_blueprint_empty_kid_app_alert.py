"""empty_kid_app_alert.yaml through the Home Assistant harness, with the real integration entity."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .blueprint_helpers import add_phone, automation_from_blueprint, notified, settle  # noqa: F401
from .platform_helpers import entity_id, setup_platform

FILE = "empty_kid_app_alert.yaml"


async def setup(hass, config_entry, fake_client, **extra):
    fake_client.set_profile(1, visible_shows=3)
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "no_visible_shows", 1)
    assert hass.states.get(sensor).state == "off"
    phone = await add_phone(hass)
    await automation_from_blueprint(
        hass, FILE, {"no_visible_shows_sensor": sensor, "notify_device": phone, **extra}
    )
    return sensor, phone


async def tick(hass, freezer, minutes):
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle()


async def test_on_for_less_than_the_time_then_off_does_not_alert(hass, config_entry, fake_client, notified, freezer):
    sensor, _ = await setup(hass, config_entry, fake_client, for_minutes=30)
    fake_client.set_profile(1, visible_shows=0)
    await settle()
    assert hass.states.get(sensor).state == "on"
    await tick(hass, freezer, 10)
    fake_client.set_profile(1, visible_shows=2)
    await settle()
    assert hass.states.get(sensor).state == "off"
    await tick(hass, freezer, 40)
    assert notified == []


async def test_on_for_the_full_time_alerts_once_naming_the_kid(hass, config_entry, fake_client, notified, freezer):
    sensor, phone = await setup(hass, config_entry, fake_client, for_minutes=30)
    fake_client.set_profile(1, visible_shows=0)
    await settle()
    await tick(hass, freezer, 29)
    assert notified == []
    await tick(hass, freezer, 2)
    assert len(notified) == 1
    assert notified[0]["device_id"] == phone
    assert "Mila" in notified[0]["message"]
    await tick(hass, freezer, 60)
    assert len(notified) == 1


async def test_zero_minutes_alerts_without_waiting(hass, config_entry, fake_client, notified):
    await setup(hass, config_entry, fake_client, for_minutes=0)
    fake_client.set_profile(1, visible_shows=0)
    await settle()
    assert len(notified) == 1
    assert "Mila" in notified[0]["message"]


async def test_unavailable_then_on_does_not_alert(hass, config_entry, fake_client, notified, freezer):
    sensor, _ = await setup(hass, config_entry, fake_client, for_minutes=5)
    hass.states.async_set(sensor, "unavailable")
    await settle()
    hass.states.async_set(sensor, "on")
    await settle()
    await tick(hass, freezer, 10)
    assert notified == []
