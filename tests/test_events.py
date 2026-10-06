"""Tests for events.diff_states and build_payload (plan 1, task T1)."""

from __future__ import annotations

from custom_components.tellybox.events import PROFILE_EVENT_TYPES, SERVER_EVENT_TYPES, TellyboxEvent, build_payload


def test_event_type_lists_are_disjoint() -> None:
    assert not set(PROFILE_EVENT_TYPES) & set(SERVER_EVENT_TYPES)


def test_build_payload_profile_event() -> None:
    event = TellyboxEvent("override_applied", 2, {"override": "extra_time", "minutes": 15, "type": "clash"})
    assert build_payload(event, instance_id="iid", device_id="dev", profile_name="Mila") == {
        "type": "override_applied",
        "device_id": "dev",
        "instance_id": "iid",
        "profile_id": 2,
        "profile_name": "Mila",
        "override": "extra_time",
        "minutes": 15,
    }


def test_build_payload_server_event_has_no_profile_keys() -> None:
    payload = build_payload(TellyboxEvent("inbox_item_arrived", None, {"pending": 3}), instance_id="iid", device_id="dev")
    assert payload == {"type": "inbox_item_arrived", "device_id": "dev", "instance_id": "iid", "pending": 3}
