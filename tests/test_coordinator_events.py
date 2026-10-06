"""The coordinator turns state changes into `tellybox_event` bus events (plan 1, T2)."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed
from pytellybox import AdminState

from custom_components.tellybox.const import (
    RECONNECT_MIN_S,
    main_device_identifier,
    profile_device_identifier,
)
from custom_components.tellybox.events import (
    EVENT_LAST_FIVE,
    EVENT_NAME,
    EVENT_OVERRIDE_APPLIED,
    EVENT_TV_UNREACHABLE,
    TellyboxEvent,
    diff_states,
)

from .conftest import INSTANCE_ID, TOKEN, URL, state_dict


def _t1_merged() -> bool:
    state = AdminState.from_dict(state_dict())
    try:
        diff_states(state, state)
    except NotImplementedError:
        return False
    return True


needs_t1 = pytest.mark.skipif(not _t1_merged(), reason="needs events.diff_states (plan 1 T1)")


def _entry_id(hass) -> str:
    return hass.config_entries.async_entries("tellybox")[0].entry_id


def coordinator(config_entry):
    return config_entry.runtime_data.coordinator


def device_id(hass, identifier) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier(identifier, _entry_id(hass))
    assert device is not None
    return device.id


def fake_diff(monkeypatch, events: list[TellyboxEvent]):
    calls: list[tuple[AdminState, AdminState]] = []

    def _diff(old: AdminState, new: AdminState) -> list[TellyboxEvent]:
        calls.append((old, new))
        return list(events)

    monkeypatch.setattr("custom_components.tellybox.coordinator.diff_states", _diff)
    return calls


async def bump(hass, fake_client, version: str = "bumped") -> None:
    """Push a state that differs from the last one (the version string), then let the coordinator process it."""
    fake_client.set_state(version=version)
    await hass.async_block_till_done()


async def reconnect(hass, fake_client, freezer) -> None:
    fake_client.break_stream()
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=RECONNECT_MIN_S + 0.1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert fake_client.stream_opens == 2


# -- plumbing, with a fake diff


async def test_first_refresh_is_baseline_without_diff(hass, monkeypatch, config_entry, patch_client):
    calls = fake_diff(monkeypatch, [])
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    c = coordinator(config_entry)
    assert c._last_state is c.data
    # only the stream's first state is diffed, and against the first refresh's state
    assert len(calls) <= 1
    assert all(old.version == new.version for old, new in calls)


async def test_profile_event_payload_and_device(hass, setup_integration, monkeypatch):
    fake_diff(monkeypatch, [TellyboxEvent(EVENT_LAST_FIVE, 1, {"minutes": 5})])
    events = async_capture_events(hass, EVENT_NAME)
    await bump(hass, setup_integration)
    assert events
    assert events[-1].data == {
        "type": EVENT_LAST_FIVE,
        "device_id": device_id(hass, profile_device_identifier(INSTANCE_ID, 1)),
        "instance_id": INSTANCE_ID,
        "profile_id": 1,
        "profile_name": "Mila",
        "minutes": 5,
    }


async def test_server_event_uses_main_device(hass, setup_integration, monkeypatch):
    fake_diff(monkeypatch, [TellyboxEvent(EVENT_TV_UNREACHABLE, None, {})])
    events = async_capture_events(hass, EVENT_NAME)
    await bump(hass, setup_integration)
    assert events[-1].data == {
        "type": EVENT_TV_UNREACHABLE,
        "device_id": device_id(hass, main_device_identifier(INSTANCE_ID)),
        "instance_id": INSTANCE_ID,
    }


async def test_diff_gets_previous_and_new_state_in_order(hass, setup_integration, monkeypatch):
    calls = fake_diff(monkeypatch, [])
    await bump(hass, setup_integration, "v1")
    await bump(hass, setup_integration, "v2")
    assert [new.version for _, new in calls] == ["v1", "v2"]
    assert calls[1][0] is calls[0][1]  # the second diff starts from the first's new state


async def test_unregistered_device_skips_that_event_only(hass, setup_integration, monkeypatch, caplog):
    registry = dr.async_get(hass)
    registry.async_remove_device(device_id(hass, profile_device_identifier(INSTANCE_ID, 2)))
    fake_diff(monkeypatch, [TellyboxEvent(EVENT_LAST_FIVE, 2, {}), TellyboxEvent(EVENT_LAST_FIVE, 1, {})])
    events = async_capture_events(hass, EVENT_NAME)
    with caplog.at_level(logging.DEBUG, logger="custom_components.tellybox.coordinator"):
        await bump(hass, setup_integration)
    assert [e.data["profile_id"] for e in events] == [1]
    assert "device not registered" in caplog.text


async def test_bad_diff_does_not_break_the_stream(hass, setup_integration, config_entry, monkeypatch, caplog):
    def boom(old, new):
        raise RuntimeError("bad diff")

    monkeypatch.setattr("custom_components.tellybox.coordinator.diff_states", boom)
    events = async_capture_events(hass, EVENT_NAME)
    await bump(hass, setup_integration)
    assert "Failed to derive Tellybox events" in caplog.text
    assert events == []
    setup_integration.set_profile(1, remaining_s=7)
    await hass.async_block_till_done()
    assert coordinator(config_entry).data.profile(1).remaining_s == 7
    assert coordinator(config_entry).last_update_success


async def test_no_events_after_stop(hass, setup_integration, config_entry, monkeypatch):
    fake_diff(monkeypatch, [TellyboxEvent(EVENT_LAST_FIVE, 1, {})])
    events = async_capture_events(hass, EVENT_NAME)
    c = coordinator(config_entry)
    await c.async_stop()
    c._apply(AdminState.from_dict({**state_dict(), "version": "late"}))  # e.g. a command result mid-unload
    await hass.async_block_till_done()
    assert events == []


async def test_unloaded_entry_fires_nothing(hass, setup_integration, config_entry, monkeypatch):
    c = coordinator(config_entry)
    fake_diff(monkeypatch, [TellyboxEvent(EVENT_LAST_FIVE, 1, {})])
    events = async_capture_events(hass, EVENT_NAME)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    c._apply(AdminState.from_dict({**state_dict(), "version": "late"}))
    setup_integration.set_profile(1, remaining_s=3)
    await hass.async_block_till_done()
    assert events == []


async def test_reconnect_keeps_baseline(hass, setup_integration, monkeypatch, freezer):
    await bump(hass, setup_integration, "before-break")
    calls = fake_diff(monkeypatch, [])
    await reconnect(hass, setup_integration, freezer)
    # the reconnect's first state is diffed against the pre-break state, not treated as a new baseline
    assert len(calls) == 1
    assert calls[0][0].version == "before-break"


# -- end to end with the real diff_states


@needs_t1
async def test_no_events_on_setup(hass, config_entry, patch_client):
    events = async_capture_events(hass, EVENT_NAME)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert events == []


@needs_t1
async def test_profile_change_fires_exactly_one_event(hass, setup_integration):
    events = async_capture_events(hass, EVENT_NAME)
    setup_integration.set_profile(1, last_five=True)
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["type"] == EVENT_LAST_FIVE
    assert events[0].data["device_id"] == device_id(hass, profile_device_identifier(INSTANCE_ID, 1))
    assert events[0].data["profile_id"] == 1
    assert events[0].data["profile_name"] == "Mila"
    assert events[0].data["instance_id"] == INSTANCE_ID


@needs_t1
async def test_reconnect_does_not_replay(hass, setup_integration, freezer):
    setup_integration.set_profile(1, last_five=True)
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_NAME)
    await reconnect(hass, setup_integration, freezer)
    # the new connection opens with the fake's (unchanged) current state: nothing new to report
    assert events == []


@needs_t1
async def test_command_result_fires_override_once(hass, setup_integration, config_entry):
    events = async_capture_events(hass, EVENT_NAME)
    c = coordinator(config_entry)
    await c.async_command(lambda: setup_integration.add_time(10, [2]))
    await hass.async_block_till_done()  # the fake also pushes the same state onto the stream
    overrides = [e for e in events if e.data["type"] == EVENT_OVERRIDE_APPLIED]
    assert len(overrides) == 1
    assert overrides[0].data["profile_id"] == 2
    assert overrides[0].data["device_id"] == device_id(hass, profile_device_identifier(INSTANCE_ID, 2))


@needs_t1
async def test_payload_has_no_url_or_token(hass, setup_integration, config_entry):
    events = async_capture_events(hass, EVENT_NAME)
    setup_integration.set_profile(1, last_five=True)
    await coordinator(config_entry).async_command(lambda: setup_integration.add_time(5, [1]))
    await hass.async_block_till_done()
    assert events
    text = repr([e.data for e in events])
    assert TOKEN not in text and URL not in text and "http" not in text


@needs_t1
async def test_unloaded_entry_fires_nothing_real_diff(hass, setup_integration, config_entry):
    c = coordinator(config_entry)
    events = async_capture_events(hass, EVENT_NAME)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    changed = state_dict()
    changed["profiles"][0]["last_five"] = True
    c._apply(AdminState.from_dict(changed))
    await hass.async_block_till_done()
    assert events == []
