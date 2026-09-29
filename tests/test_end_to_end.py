"""End to end: the integration with the real pytellybox client against pytellybox's mock Tellybox over HTTP."""

from __future__ import annotations

import pytest
from homeassistant.helpers import entity_registry as er
from pytellybox.mock import MockTellybox
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tellybox.const import CONF_CONTROL, CONF_TOKEN, CONF_URL, DOMAIN

TOKEN = "tbx_e2e"


@pytest.fixture
async def mock_tellybox(socket_enabled):
    mock = MockTellybox(token=TOKEN, keepalive_s=0.5)
    url = await mock.start("127.0.0.1")
    yield mock, url
    await mock.stop()


async def test_setup_press_and_stream(hass, mock_tellybox):
    mock, url = mock_tellybox
    info_id = mock.state["instance_id"]
    entry = MockConfigEntry(domain=DOMAIN, unique_id=info_id, data={CONF_URL: url, CONF_TOKEN: TOKEN},
                            options={CONF_CONTROL: True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    time_left_2 = reg.async_get_entity_id("sensor", DOMAIN, f"{info_id}_profile_2_time_left")
    add_15_2 = reg.async_get_entity_id("button", DOMAIN, f"{info_id}_profile_2_add_15_minutes")
    assert float(hass.states.get(time_left_2).state) == 0

    await hass.services.async_call("button", "press", {"entity_id": add_15_2}, blocking=True)
    await hass.async_block_till_done()
    assert float(hass.states.get(time_left_2).state) == 15  # suggested unit: minutes

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
