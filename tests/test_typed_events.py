"""Typed server events (plan 13, T4): source selection, mapping to bus events, no duplicates, parity."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytellybox import AdminState, ServerEvent, TellyboxConnectionError
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed

from custom_components.tellybox.const import RECONNECT_MIN_S, main_device_identifier, profile_device_identifier
from custom_components.tellybox.events import EVENT_NAME, from_server_event

from .conftest import INSTANCE_ID, state_dict

TYPED_CAPS = ("state", "events", "overrides", "profiles", "history", "typed_events")


def _device_id(hass, identifier) -> str:
    entry = hass.config_entries.async_entries("tellybox")[0]
    device = dr.async_get(hass).async_get_device_by_identifier(identifier, entry.entry_id)
    assert device is not None
    return device.id


async def _setup(hass, config_entry, fake, *, typed: bool) -> None:
    fake.capabilities = TYPED_CAPS if typed else fake.capabilities
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def typed(hass, config_entry, patch_client):
    await _setup(hass, config_entry, patch_client, typed=True)
    return patch_client


async def _reconnect(hass, fake, freezer, opens: int) -> None:
    fake.break_stream()
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=RECONNECT_MIN_S + 0.1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert fake.stream_opens == opens


# -- source selection


async def test_typed_mode_uses_typed_stream(typed):
    assert typed.stream_modes == [True]


async def test_fallback_uses_events(hass, config_entry, patch_client):
    await _setup(hass, config_entry, patch_client, typed=False)
    assert patch_client.stream_modes == [False]


async def test_info_is_read_before_each_connect_and_mode_follows_it(hass, config_entry, patch_client, freezer):
    await _setup(hass, config_entry, patch_client, typed=False)
    infos = patch_client.calls.count(("info",))
    patch_client.capabilities = TYPED_CAPS  # Tellybox was upgraded
    await _reconnect(hass, patch_client, freezer, 2)
    assert patch_client.calls.count(("info",)) == infos + 1
    assert patch_client.stream_modes == [False, True]
    patch_client.capabilities = ("state", "events")  # and downgraded
    await _reconnect(hass, patch_client, freezer, 3)
    assert patch_client.stream_modes == [False, True, False]


async def test_failing_info_means_fallback(hass, config_entry, patch_client, freezer, caplog):
    await _setup(hass, config_entry, patch_client, typed=True)

    async def broken():
        raise TellyboxConnectionError("no info")

    patch_client.info = broken
    with caplog.at_level(logging.DEBUG, logger="custom_components.tellybox.coordinator"):
        await _reconnect(hass, patch_client, freezer, 2)
    assert patch_client.stream_modes == [True, False]
    assert "Can't read Tellybox's capabilities" in caplog.text


# -- mapping to bus events


async def test_stopped_watching_carries_reason(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.set_profile(1, watching=False)
    typed.push_event("playback_stopped", [1], reason="finished", position_s=600, episode_id=4, show_id=2,
                     title="Alongside", show="Harbour Pups", target="tv", label="TV")
    await hass.async_block_till_done()
    assert [e.data for e in events] == [{
        "type": "stopped_watching", "device_id": _device_id(hass, profile_device_identifier(INSTANCE_ID, 1)),
        "instance_id": INSTANCE_ID, "profile_id": 1, "profile_name": "Mila", "reason": "finished",
        "position_s": 600, "episode_id": 4, "show_id": 2, "title": "Alongside", "show": "Harbour Pups",
        "target": "tv", "label": "TV",
    }]


async def test_override_applied_extra_time_has_minutes_and_source(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.push_event("override_applied", [1], kind="extra_minutes", value=15, source="Kitchen tablet")
    await hass.async_block_till_done()
    assert len(events) == 1
    data = events[0].data
    assert (data["type"], data["override"], data["minutes"], data["source"]) == (
        "override_applied", "extra_time", 15, "Kitchen tablet")


async def test_override_applied_admin_page_has_source_none(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.push_event("override_applied", [2], kind="block", value=None, source=None)
    await hass.async_block_till_done()
    assert events[0].data["override"] == "blocked"
    assert events[0].data["source"] is None
    assert "minutes" not in events[0].data


@pytest.mark.parametrize(("kind", "name"), [("unlimited", "unlimited"), ("clear", "cleared"), ("stop_now", "stop_now")])
async def test_override_kinds(kind, name):
    [event] = from_server_event(ServerEvent.from_dict({"type": "override_applied", "profile_ids": [1], "kind": kind}))
    assert event.data["override"] == name


async def test_group_event_fans_out_per_kid(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.push_event("last_five", [1, 2], remaining_s=290)
    await hass.async_block_till_done()
    assert [(e.data["profile_id"], e.data["profile_name"], e.data["remaining_s"]) for e in events] == [
        (1, "Mila", 290), (2, "Noah", 290)]
    assert events[0].data["device_id"] != events[1].data["device_id"]


async def test_server_level_events(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.push_event("inbox_item_arrived", pending=3, new_items=1)
    typed.push_event("download_ready", held_ready=2, new_ready=1)
    await hass.async_block_till_done()
    main = _device_id(hass, main_device_identifier(INSTANCE_ID))
    assert [e.data for e in events] == [
        {"type": "inbox_item_arrived", "device_id": main, "instance_id": INSTANCE_ID, "pending": 3, "new_items": 1},
        {"type": "download_ready", "device_id": main, "instance_id": INSTANCE_ID, "held_ready": 2, "new_ready": 1},
    ]


async def test_unknown_type_passes_through(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.push_event("something_new", [1], flavour="odd")
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == {
        "type": "something_new", "device_id": _device_id(hass, main_device_identifier(INSTANCE_ID)),
        "instance_id": INSTANCE_ID, "flavour": "odd",
    }


async def test_unknown_kid_is_skipped(hass, typed, caplog):
    events = async_capture_events(hass, EVENT_NAME)
    with caplog.at_level(logging.DEBUG, logger="custom_components.tellybox.coordinator"):
        typed.push_event("last_five", [99, 1], remaining_s=1)
        await hass.async_block_till_done()
    assert [e.data["profile_id"] for e in events] == [1]
    assert "unknown kid" in caplog.text


async def test_bad_server_event_does_not_break_the_stream(hass, typed, config_entry, monkeypatch, caplog):
    def boom(event):
        raise RuntimeError("bad")

    monkeypatch.setattr("custom_components.tellybox.coordinator.from_server_event", boom)
    typed.push_event("last_five", [1], remaining_s=1)
    await hass.async_block_till_done()
    assert "Failed to handle Tellybox event" in caplog.text
    typed.set_profile(1, remaining_s=7)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.coordinator.data.profile(1).remaining_s == 7


# -- the diff in typed mode


async def test_tv_events_still_come_from_the_diff(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.set_state(tv={**state_dict()["tv"], "reachable": False})
    await hass.async_block_till_done()
    typed.set_state(tv={**state_dict()["tv"], "reachable": True})
    await hass.async_block_till_done()
    assert [e.data["type"] for e in events] == ["tv_unreachable", "tv_reachable"]
    assert all(e.data["device_id"] == _device_id(hass, main_device_identifier(INSTANCE_ID)) for e in events)


async def test_nothing_else_comes_from_the_diff_in_typed_mode(hass, typed):
    events = async_capture_events(hass, EVENT_NAME)
    typed.set_profile(1, last_five=True)
    typed.set_profile(1, watching=False)
    typed.set_profile(1, can_start=False, reason="allowance")
    typed.set_profile(1, unlimited=True)
    typed.set_profile(1, extra_s=2000)
    await hass.async_block_till_done()
    assert events == []


async def test_each_typed_type_fires_once(hass, typed):
    """State changes that would make the diff fire the same event must not duplicate the server's event."""
    events = async_capture_events(hass, EVENT_NAME)
    cases = [
        ("time_up", dict(profile_ids=[1], reason="allowance"), dict(can_start=False, reason="allowance")),
        ("last_five", dict(profile_ids=[1], remaining_s=299), dict(last_five=True)),
        ("playback_stopped", dict(profile_ids=[1], reason="stopped"), dict(watching=False)),
        ("playback_started", dict(profile_ids=[1], episode_id=4), dict(watching=True)),
        ("override_applied", dict(profile_ids=[1], kind="extra_minutes", value=10), dict(extra_s=1500)),
    ]
    for type_, fields, change in cases:
        typed.set_profile(1, **change)  # the state first, then the event, as Tellybox orders them
        typed.push_event(type_, **fields)
    typed.push_event("inbox_item_arrived", pending=1, new_items=1)
    typed.push_event("download_ready", held_ready=1, new_ready=1)
    await hass.async_block_till_done()
    assert [e.data["type"] for e in events] == [
        "time_up", "last_five_minutes", "stopped_watching", "started_watching", "override_applied",
        "inbox_item_arrived", "download_ready"]


async def test_command_result_does_not_duplicate_typed_override(hass, typed, config_entry):
    events = async_capture_events(hass, EVENT_NAME)
    await config_entry.runtime_data.coordinator.async_command(lambda: typed.add_time(10, [2]))
    typed.push_event("override_applied", [2], kind="extra_minutes", value=10, source=None)
    await hass.async_block_till_done()
    assert [e.data["type"] for e in events] == ["override_applied"]


# -- parity between the two sources


def _scenario_states(fake) -> list[tuple[dict, tuple | None]]:
    return [
        (dict(watching=True), ("playback_started", dict(episode_id=4, show_id=2, title="Alongside",
                                                        show="Harbour Pups", target="tv", label="TV"))),
        (dict(last_five=True), ("last_five", dict(remaining_s=299))),
        (dict(can_start=False, reason="allowance"), ("time_up", dict(reason="allowance"))),
        (dict(watching=False), ("playback_stopped", dict(reason="time_up", position_s=600, episode_id=4,
                                                         show_id=2, title="Alongside", show="Harbour Pups",
                                                         target="tv", label="TV"))),
    ]


async def _run_scenario(hass, fake, *, typed_mode: bool) -> list[dict]:
    fake.set_profile(1, watching=False)  # start from "not watching"; nothing captured yet
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_NAME)
    for change, event in _scenario_states(fake):
        fake.set_profile(1, **change)
        if typed_mode:
            fake.push_event(event[0], [1], **event[1])
        await hass.async_block_till_done()
    return [e.data for e in events]


async def test_parity_between_typed_and_fallback(hass, config_entry, patch_client):
    await _setup(hass, config_entry, patch_client, typed=False)
    fallback = await _run_scenario(hass, patch_client, typed_mode=False)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    # a fresh Tellybox, now with typed events
    patch_client.state_data = state_dict()
    patch_client.capabilities = TYPED_CAPS
    patch_client.stream_modes.clear()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert patch_client.stream_modes == [True]
    typed_events = await _run_scenario(hass, patch_client, typed_mode=True)

    assert [e["type"] for e in fallback] == [
        "started_watching", "last_five_minutes", "time_up", "stopped_watching"]
    assert [e["type"] for e in typed_events] == [e["type"] for e in fallback]
    for old, new in zip(fallback, typed_events, strict=True):
        assert {k: new[k] for k in old} == old  # identical wherever the fallback has a key
        assert {"type", "device_id", "instance_id", "profile_id", "profile_name"} <= set(new)
    assert typed_events[3]["reason"] == "time_up" and "reason" not in fallback[3]


# -- lifecycle


async def test_reconnect_in_typed_mode_synthesises_nothing(hass, typed, freezer):
    typed.set_profile(1, last_five=True)
    typed.push_event("last_five", [1], remaining_s=1)
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_NAME)
    infos = typed.calls.count(("info",))
    await _reconnect(hass, typed, freezer, 2)
    assert typed.calls.count(("info",)) == infos + 1
    assert typed.stream_modes == [True, True]
    assert events == []
    typed.push_event("download_ready", held_ready=1, new_ready=1)  # and the new connection delivers events
    await hass.async_block_till_done()
    assert [e.data["type"] for e in events] == ["download_ready"]


async def test_no_typed_event_while_unloading(hass, typed, config_entry):
    c = config_entry.runtime_data.coordinator
    events = async_capture_events(hass, EVENT_NAME)
    await c.async_stop()
    c._handle_server_event(ServerEvent.from_dict({"type": "last_five", "profile_ids": [1]}))
    await hass.async_block_till_done()
    assert events == []


def test_from_server_event_is_pure_and_total():
    assert from_server_event(ServerEvent.from_dict({"type": ""})) == []
    assert from_server_event(ServerEvent.from_dict({"type": "last_five"})) == []  # no kids named
