"""Device triggers: listing per device kind and firing on matching `tellybox_event`s only."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from homeassistant.components import automation
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from custom_components.tellybox.const import DOMAIN, main_device_identifier, profile_device_identifier
from custom_components.tellybox.device_trigger import async_get_triggers
from custom_components.tellybox.events import EVENT_NAME, PROFILE_EVENT_TYPES, SERVER_EVENT_TYPES

from .conftest import INSTANCE_ID


def _device(hass, identifier):
    return next(d for d in dr.async_get(hass).devices if identifier in d.identifiers)


async def test_kid_device_triggers(hass, setup_integration):
    kid = _device(hass, profile_device_identifier(INSTANCE_ID, 1))
    triggers = await async_get_triggers(hass, kid.id)
    assert [t["type"] for t in triggers] == list(PROFILE_EVENT_TYPES)
    for t in triggers:
        assert t["platform"] == "device" and t["domain"] == DOMAIN and t["device_id"] == kid.id


async def test_tellybox_device_triggers(hass, setup_integration):
    main = _device(hass, main_device_identifier(INSTANCE_ID))
    triggers = await async_get_triggers(hass, main.id)
    assert [t["type"] for t in triggers] == list(SERVER_EVENT_TYPES)
    assert all(t["device_id"] == main.id for t in triggers)


async def test_foreign_device_has_no_triggers(hass, setup_integration):
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("other", "abc")}
    )
    assert await async_get_triggers(hass, device.id) == []
    assert await async_get_triggers(hass, "does-not-exist") == []


@pytest.fixture
async def calls(hass):
    return async_mock_service(hass, "test", "automation")


async def _automation(hass, device_id, event_type):
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "device", "domain": DOMAIN, "device_id": device_id, "type": event_type},
                "action": {"service": "test.automation", "data": {"seen": "yes"}},
            }
        },
    )
    await hass.async_block_till_done()


async def test_automation_runs_only_for_matching_event(hass, setup_integration, calls):
    mila = _device(hass, profile_device_identifier(INSTANCE_ID, 1))
    noah = _device(hass, profile_device_identifier(INSTANCE_ID, 2))
    await _automation(hass, mila.id, "time_up")

    hass.bus.async_fire(EVENT_NAME, {"device_id": noah.id, "type": "time_up"})
    await hass.async_block_till_done()
    assert calls == []

    hass.bus.async_fire(EVENT_NAME, {"device_id": mila.id, "type": "started_watching"})
    await hass.async_block_till_done()
    assert calls == []

    hass.bus.async_fire(EVENT_NAME, {"device_id": mila.id, "type": "time_up", "profile_id": 1})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_server_trigger_runs(hass, setup_integration, calls):
    main = _device(hass, main_device_identifier(INSTANCE_ID))
    await _automation(hass, main.id, "tv_unreachable")
    hass.bus.async_fire(EVENT_NAME, {"device_id": main.id, "type": "tv_unreachable"})
    await hass.async_block_till_done()
    assert len(calls) == 1
