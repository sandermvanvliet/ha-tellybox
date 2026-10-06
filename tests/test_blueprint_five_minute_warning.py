"""five_minute_warning.yaml through the Home Assistant harness."""

from __future__ import annotations

from homeassistant.const import Platform
from pytest_homeassistant_custom_component.common import async_mock_service

from .blueprint_helpers import automation_from_blueprint
from .platform_helpers import entity_id, setup_platform

FILE = "five_minute_warning.yaml"
INPUTS = {
    "warning_actions": [
        {"action": "test.warn", "data": {"kid": "{{ kid }}", "device": "{{ kid_device_id }}"}},
    ]
}


async def test_plain_binary_sensor_off_to_on_runs_actions_once(hass):
    calls = async_mock_service(hass, "test", "warn")
    hass.states.async_set("binary_sensor.plain", "off")
    await automation_from_blueprint(hass, FILE, {"last_five_sensor": "binary_sensor.plain", **INPUTS})

    hass.states.async_set("binary_sensor.plain", "on")
    await hass.async_block_till_done()

    assert len(calls) == 1
    # No device behind the entity: kid renders empty, it does not raise.
    assert calls[0].data["kid"] == ""


async def test_plain_binary_sensor_staying_on_does_not_rerun(hass):
    calls = async_mock_service(hass, "test", "warn")
    hass.states.async_set("binary_sensor.plain", "off")
    await automation_from_blueprint(hass, FILE, {"last_five_sensor": "binary_sensor.plain", **INPUTS})
    hass.states.async_set("binary_sensor.plain", "on")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.plain", "on", {"changed": 1})  # attribute change only
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_unavailable_to_on_does_fire(hass):
    """Actual behaviour: `to: on` with no `from` also fires for unavailable -> on (e.g. a reconnect)."""
    calls = async_mock_service(hass, "test", "warn")
    hass.states.async_set("binary_sensor.plain", "unavailable")
    await automation_from_blueprint(hass, FILE, {"last_five_sensor": "binary_sensor.plain", **INPUTS})

    hass.states.async_set("binary_sensor.plain", "on")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_kid_sensor_renders_device_name(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes", 1)  # Mila, not in the last five yet
    assert hass.states.get(sensor).state == "off"
    calls = async_mock_service(hass, "test", "warn")
    await automation_from_blueprint(hass, FILE, {"last_five_sensor": sensor, **INPUTS})

    fake_client.set_profile(1, last_five=True)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["kid"] == "Mila"
    assert calls[0].data["device"]


async def test_tellybox_device_sensor_renders_tellybox(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client, Platform.BINARY_SENSOR)
    sensor = entity_id(hass, "binary_sensor", "last_five_minutes")
    calls = async_mock_service(hass, "test", "warn")
    await automation_from_blueprint(hass, FILE, {"last_five_sensor": sensor, **INPUTS})

    fake_client.set_state(group={**fake_client.state_data["group"], "last_five": True})
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["kid"] == "Tellybox"
