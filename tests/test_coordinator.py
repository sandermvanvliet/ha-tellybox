"""The push coordinator: events, reconnect, availability, reauth, commands."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytellybox import (
    AdminState,
    TellyboxAuthError,
    TellyboxConnectionError,
    TellyboxForbiddenError,
    TellyboxRequestError,
    TellyboxTimeUpError,
    TellyboxUnavailableError,
)

from custom_components.tellybox.const import RECONNECT_MAX_S, RECONNECT_MIN_S, UNAVAILABLE_AFTER_S

from .helpers import core, no_platforms  # noqa: F401


def coordinator(config_entry):
    return config_entry.runtime_data.coordinator


async def tick(hass, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_first_refresh_and_event_updates_data(hass, core, config_entry):
    c = coordinator(config_entry)
    assert c.data.profile(1).remaining_s == 1790
    assert c.update_interval is None
    core.set_profile(1, remaining_s=100)
    await hass.async_block_till_done()
    assert c.data.profile(1).remaining_s == 100


async def test_last_watchers(hass, core, config_entry):
    c = coordinator(config_entry)
    assert c.last_watchers == (1,)
    core.set_state(now_playing=None)
    await hass.async_block_till_done()
    assert c.last_watchers == (1,)  # remembered
    playing = {"episode_id": 4, "show_id": 2, "title": "A", "show": "S", "state": "playing", "position_s": 1,
               "duration_s": 2, "profile_ids": [1, 2]}
    core.set_state(now_playing=playing)
    await hass.async_block_till_done()
    assert c.last_watchers == (1, 2)


async def test_reconnects_with_backoff_and_stays_available(hass, core, config_entry, freezer):
    c = coordinator(config_entry)
    core.break_stream()
    await hass.async_block_till_done()
    assert core.stream_opens == 1
    assert c.last_update_success  # a blip: still available
    await tick(hass, freezer, RECONNECT_MIN_S + 0.1)
    assert core.stream_opens == 2
    # the reconnect delivered the state: still fine, timer cancelled
    core.set_profile(1, remaining_s=5)
    await hass.async_block_till_done()
    assert c.data.profile(1).remaining_s == 5 and c.last_update_success


async def test_backoff_doubles_up_to_max(hass, core, config_entry, freezer):
    core.fail_with = TellyboxConnectionError("down")
    core.break_stream()
    await hass.async_block_till_done()
    opens = core.stream_opens
    waits = []
    delay = RECONNECT_MIN_S
    for _ in range(9):
        waits.append(delay)
        await tick(hass, freezer, delay + 0.1)
        assert core.stream_opens == opens + 1
        opens += 1
        delay = min(delay * 2, RECONNECT_MAX_S)
    assert waits[-1] == RECONNECT_MAX_S
    # not yet time for another attempt
    await tick(hass, freezer, RECONNECT_MAX_S - 5)
    assert core.stream_opens == opens


async def test_unavailable_after_threshold_and_recovers(hass, core, config_entry, freezer):
    c = coordinator(config_entry)
    calls = []
    c.async_add_listener(lambda: calls.append(c.last_update_success))
    core.fail_with = TellyboxConnectionError("down")
    core.break_stream()
    await hass.async_block_till_done()
    await tick(hass, freezer, UNAVAILABLE_AFTER_S - 10)
    assert c.last_update_success
    await tick(hass, freezer, 11)
    assert not c.last_update_success
    assert calls and calls[-1] is False
    core.fail_with = None
    await tick(hass, freezer, RECONNECT_MAX_S + 1)
    assert c.last_update_success
    assert calls[-1] is True


async def test_stream_401_starts_reauth_and_stops(hass, core, config_entry, freezer):
    opens = core.stream_opens
    core.fail_with = TellyboxAuthError("revoked")
    core.break_stream()
    await hass.async_block_till_done()
    await tick(hass, freezer, RECONNECT_MIN_S + 0.1)
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())
    reconnects = core.stream_opens
    await tick(hass, freezer, RECONNECT_MAX_S + 1)
    assert core.stream_opens == reconnects  # stopped
    assert reconnects == opens + 1


async def test_unload_cancels_stream(hass, core, config_entry):
    c = coordinator(config_entry)
    task = c._task
    assert task is not None and not task.done()
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert c._task is None and task.done()


async def test_command_applies_returned_state_at_once(hass, core, config_entry):
    c = coordinator(config_entry)
    result = await c.async_command(lambda: core.add_time(15, [2]))
    assert isinstance(result, AdminState)
    assert c.data.profile(2).remaining_s == 900


@pytest.mark.parametrize(
    ("exc", "key"),
    [(TellyboxForbiddenError("x"), "forbidden"), (TellyboxTimeUpError("x"), "time_up"),
     (TellyboxUnavailableError("x"), "unavailable"), (TellyboxConnectionError("x"), "connection"),
     (TellyboxRequestError("minutes must be 1..240"), "request")],
)
async def test_command_error_mapping(hass, core, config_entry, exc, key):
    async def boom():
        raise exc

    with pytest.raises(HomeAssistantError) as err:
        await coordinator(config_entry).async_command(boom)
    assert err.value.translation_key == key and err.value.translation_domain == "tellybox"
    if key == "request":
        assert err.value.translation_placeholders == {"detail": "minutes must be 1..240"}


async def test_command_401_starts_reauth(hass, core, config_entry):
    async def boom():
        raise TellyboxAuthError("x")

    with pytest.raises(HomeAssistantError) as err:
        await coordinator(config_entry).async_command(boom)
    assert err.value.translation_key == "auth"
    await hass.async_block_till_done()
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())
