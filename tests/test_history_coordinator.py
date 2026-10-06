"""The history coordinator (HA-12): created with the capability, polled, refreshed at the rollover."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytellybox import TellyboxAuthError, TellyboxConnectionError
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.tellybox.const import CAPABILITY_HISTORY, HISTORY_POLL_S

from .platform_helpers import push_state, setup_platform


def _history_calls(fake) -> list[tuple]:
    return [c for c in fake.calls if c[0] == "history"]


async def test_created_with_the_capability(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    history = config_entry.runtime_data.history
    assert history is not None
    assert history.update_interval == timedelta(seconds=HISTORY_POLL_S) == timedelta(minutes=30)
    assert history.last_update_success
    assert _history_calls(fake_client) == [("history", 8, None)]
    assert history.data.profiles[0].days[1].used_s == 3600


async def test_not_created_without_the_capability(hass, config_entry, fake_client):
    fake_client.capabilities = tuple(c for c in fake_client.capabilities if c != CAPABILITY_HISTORY)
    await setup_platform(hass, config_entry, fake_client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.history is None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert _history_calls(fake_client) == []


async def test_failing_info_means_no_history(hass, config_entry, fake_client):
    async def broken_info():
        raise TellyboxConnectionError("no")

    fake_client.info = broken_info
    await setup_platform(hass, config_entry, fake_client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.history is None
    assert _history_calls(fake_client) == []


async def test_polls_every_half_hour(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HISTORY_POLL_S + 5))
    await hass.async_block_till_done()
    assert len(_history_calls(fake_client)) == 2


async def test_refreshes_when_the_day_rolls_over(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    assert len(_history_calls(fake_client)) == 1
    fake_client.set_state(group={**fake_client.state_data["group"]})  # same day: no refresh
    await hass.async_block_till_done()
    assert len(_history_calls(fake_client)) == 1
    fake_client.set_state(day={**fake_client.state_data["day"], "date": "2026-09-30"})
    await hass.async_block_till_done()
    assert len(_history_calls(fake_client)) == 2
    await push_state(hass, fake_client)  # the same new day again: still no refresh
    assert len(_history_calls(fake_client)) == 2


async def test_auth_error_starts_reauth(hass, config_entry, fake_client):
    fake_client.history_error = TellyboxAuthError("no")
    await setup_platform(hass, config_entry, fake_client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_other_errors_keep_the_last_data_and_dont_fail_setup(hass, config_entry, fake_client):
    fake_client.history_error = TellyboxConnectionError("down")
    await setup_platform(hass, config_entry, fake_client)
    history = config_entry.runtime_data.history
    assert config_entry.state is ConfigEntryState.LOADED
    assert history is not None and history.data is None and not history.last_update_success

    fake_client.history_error = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=HISTORY_POLL_S + 5))
    await hass.async_block_till_done()
    assert history.last_update_success
    first = history.data

    fake_client.history_error = TimeoutError()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2 * HISTORY_POLL_S + 10))
    await hass.async_block_till_done()
    assert not history.last_update_success
    assert history.data is first


async def test_unload_leaves_no_timers(hass, config_entry, fake_client):
    await setup_platform(hass, config_entry, fake_client)
    fake_client.set_state(day={**fake_client.state_data["day"], "date": "2026-09-30"})  # a debounce timer
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    calls = len(_history_calls(fake_client))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert len(_history_calls(fake_client)) == calls
