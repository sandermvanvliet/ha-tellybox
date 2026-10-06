"""tv_off_at_time_up.yaml through the Home Assistant harness."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from .blueprint_helpers import automation_from_blueprint

FILE = "tv_off_at_time_up.yaml"
SENSOR = "binary_sensor.time_up"
PLAYER = "media_player.tellybox"
TV = "media_player.living_room_tv"


async def settle():
    """Let the automation run progress. `async_block_till_done` would wait for a run sitting in a delay."""
    for _ in range(20):
        await asyncio.sleep(0)


async def setup(hass, *, player="playing", **extra):
    calls = async_mock_service(hass, "media_player", "turn_off")
    hass.states.async_set(SENSOR, "off")
    hass.states.async_set(PLAYER, player)
    await automation_from_blueprint(
        hass,
        FILE,
        {"time_up_sensor": SENSOR, "tellybox_player": PLAYER, "tv": TV, **extra},
    )
    return calls


async def tick(hass, freezer, minutes):
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass, dt_util.utcnow())
    await settle()


async def test_player_idle_turns_tv_off_after_grace(hass, freezer):
    calls = await setup(hass, player="idle")
    hass.states.async_set(SENSOR, "on")
    await settle()
    assert calls == []  # grace not elapsed

    await tick(hass, freezer, 1)
    assert calls == []
    await tick(hass, freezer, 1)
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == [TV]


async def test_zero_grace_turns_off_immediately(hass):
    calls = await setup(hass, player="off", grace_minutes=0)
    hass.states.async_set(SENSOR, "on")
    await settle()
    assert len(calls) == 1


async def test_playing_then_idle_turns_off_only_after_idle(hass, freezer):
    calls = await setup(hass, player="playing")
    hass.states.async_set(SENSOR, "on")
    await settle()
    await tick(hass, freezer, 10)
    assert calls == []  # episode still playing, time up is not playback stopped

    hass.states.async_set(PLAYER, "idle")
    await settle()
    assert calls == []
    await tick(hass, freezer, 2)
    assert len(calls) == 1


async def test_time_up_off_during_wait_no_tv_off(hass, freezer):
    calls = await setup(hass, player="playing")
    hass.states.async_set(SENSOR, "on")
    await settle()
    hass.states.async_set(SENSOR, "off")  # a parent added time
    await settle()
    hass.states.async_set(PLAYER, "idle")
    await settle()
    await tick(hass, freezer, 5)
    assert calls == []


async def test_wait_timeout_does_nothing_even_if_player_idles_later(hass, freezer):
    """Chosen behaviour: when playback is still running at the timeout the TV is NOT turned off."""
    calls = await setup(hass, player="playing", wait_timeout_minutes=30)
    hass.states.async_set(SENSOR, "on")
    await settle()
    await tick(hass, freezer, 31)
    await tick(hass, freezer, 5)
    assert calls == []

    hass.states.async_set(PLAYER, "idle")  # the run is over, so this does not turn the TV off
    await settle()
    await tick(hass, freezer, 5)
    assert calls == []


async def test_time_up_off_during_grace_no_tv_off(hass, freezer):
    calls = await setup(hass, player="idle")
    hass.states.async_set(SENSOR, "on")
    await settle()
    await tick(hass, freezer, 1)
    hass.states.async_set(SENSOR, "off")
    await settle()
    await tick(hass, freezer, 5)
    assert calls == []


async def test_unavailable_to_on_does_not_trigger(hass, freezer):
    calls = await setup(hass, player="idle", grace_minutes=0)
    hass.states.async_set(SENSOR, "unavailable")
    await settle()
    hass.states.async_set(SENSOR, "on")
    await settle()
    assert calls == []
