"""Tests for events.diff_states and build_payload (plan 1, task T1)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

from pytellybox import AdminState

from custom_components.tellybox.events import (
    PROFILE_EVENT_TYPES,
    SERVER_EVENT_TYPES,
    TellyboxEvent,
    build_payload,
    diff_states,
)

from .conftest import state_dict


def test_event_type_lists_are_disjoint() -> None:
    assert not set(PROFILE_EVENT_TYPES) & set(SERVER_EVENT_TYPES)


def test_download_ready_is_a_server_event_type() -> None:
    from custom_components.tellybox.events import EVENT_DOWNLOAD_READY

    assert EVENT_DOWNLOAD_READY == "download_ready"
    assert EVENT_DOWNLOAD_READY in SERVER_EVENT_TYPES and EVENT_DOWNLOAD_READY not in PROFILE_EVENT_TYPES


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


# --- diff_states -----------------------------------------------------------------------------------------------


def base() -> AdminState:
    """Mila (1): watching, can start, extra 900 s. Noah (2): out of time (allowance), last five, not watching."""
    return AdminState.from_dict(state_dict())


def with_profile(state: AdminState, profile_id: int, **changes) -> AdminState:
    profiles = tuple(replace(p, **changes) if p.id == profile_id else p for p in state.profiles)
    return replace(state, profiles=profiles)


def kinds(events: list[TellyboxEvent]) -> list[tuple]:
    return [(e.type, e.profile_id) for e in events]


def test_identical_states_give_no_events() -> None:
    assert diff_states(base(), base()) == []


def test_time_up_with_reason() -> None:
    old = with_profile(base(), 1, can_start=True)
    new = with_profile(old, 1, can_start=False, reason="session_max")
    assert diff_states(old, new) == [TellyboxEvent("time_up", 1, {"reason": "session_max"})]


def test_time_up_reason_none_from_older_server() -> None:
    old = with_profile(base(), 1, can_start=True)
    new = with_profile(old, 1, can_start=False, reason=None)
    assert diff_states(old, new) == [TellyboxEvent("time_up", 1, {"reason": None})]


def test_time_up_not_repeated_and_no_counterpart() -> None:
    up = with_profile(base(), 1, can_start=False, reason="allowance")
    assert diff_states(up, up) == []
    assert diff_states(up, with_profile(up, 1, can_start=True, reason=None)) == []


def test_last_five_edge_only() -> None:
    old = with_profile(base(), 1, last_five=False)
    new = with_profile(old, 1, last_five=True)
    assert diff_states(old, new) == [TellyboxEvent("last_five_minutes", 1, {})]
    assert diff_states(new, old) == []


def test_started_and_stopped_watching() -> None:
    idle = with_profile(base(), 1, watching=False)
    watching = with_profile(base(), 1, watching=True)
    assert diff_states(idle, watching) == [TellyboxEvent("started_watching", 1, {})]
    assert diff_states(watching, idle) == [TellyboxEvent("stopped_watching", 1, {})]


def test_tv_both_directions() -> None:
    up = base()
    down = replace(up, tv=replace(up.tv, reachable=False, connection="unreachable"))
    assert diff_states(up, down) == [TellyboxEvent("tv_unreachable", None, {})]
    assert diff_states(down, up) == [TellyboxEvent("tv_reachable", None, {})]
    assert diff_states(down, down) == []


def test_extra_time_added() -> None:
    old = base()
    new = with_profile(old, 1, extra_s=900 + 15 * 60)
    assert diff_states(old, new) == [TellyboxEvent("override_applied", 1, {"override": "extra_time", "minutes": 15})]


def test_extra_time_from_none_and_under_a_minute() -> None:
    old = with_profile(base(), 1, extra_s=None)
    assert diff_states(old, with_profile(old, 1, extra_s=600)) == [
        TellyboxEvent("override_applied", 1, {"override": "extra_time", "minutes": 10})
    ]
    assert diff_states(old, with_profile(old, 1, extra_s=30)) == []


def test_extra_time_decrease_is_ignored() -> None:
    old = base()
    assert diff_states(old, with_profile(old, 1, extra_s=0)) == []
    assert diff_states(old, with_profile(old, 1, extra_s=None)) == []


def test_unlimited_applied_and_cleared() -> None:
    old = base()
    on = with_profile(old, 1, unlimited=True)
    assert diff_states(old, on) == [TellyboxEvent("override_applied", 1, {"override": "unlimited"})]
    assert diff_states(on, old) == [TellyboxEvent("override_applied", 1, {"override": "cleared"})]


def test_blocked_applied_and_cleared() -> None:
    old = base()
    on = with_profile(old, 1, blocked=True)
    assert diff_states(old, on) == [TellyboxEvent("override_applied", 1, {"override": "blocked"})]
    assert diff_states(on, old) == [TellyboxEvent("override_applied", 1, {"override": "cleared"})]


def test_cleared_suppressed_on_day_change() -> None:
    on = with_profile(with_profile(base(), 1, unlimited=True), 2, blocked=True)
    new = replace(
        with_profile(with_profile(on, 1, unlimited=False), 2, blocked=False),
        day=replace(on.day, date=date(2026, 9, 30)),
    )
    assert diff_states(on, new) == []


def test_cleared_reported_on_same_day() -> None:
    on = with_profile(base(), 1, unlimited=True)
    new = replace(with_profile(on, 1, unlimited=False), day=replace(on.day))
    assert kinds(diff_states(on, new)) == [("override_applied", 1)]


def test_day_change_does_not_suppress_other_overrides() -> None:
    old = base()
    new = replace(with_profile(old, 1, blocked=True, extra_s=900 + 300), day=replace(old.day, date=date(2026, 9, 30)))
    assert [e.data for e in diff_states(old, new)] == [
        {"override": "extra_time", "minutes": 5},
        {"override": "blocked"},
    ]


def test_two_kids_in_one_state_follow_profile_order() -> None:
    old = with_profile(with_profile(base(), 1, watching=True), 2, watching=False, last_five=False)
    new = with_profile(with_profile(old, 1, watching=False), 2, watching=True, last_five=True)
    assert kinds(diff_states(old, new)) == [
        ("stopped_watching", 1),
        ("last_five_minutes", 2),
        ("started_watching", 2),
    ]


def test_new_kid_is_baseline() -> None:
    new = base()
    old = replace(new, profiles=tuple(p for p in new.profiles if p.id != 2))
    assert diff_states(old, new) == []


def test_disappearing_kid_yields_nothing() -> None:
    old = base()
    new = replace(old, profiles=tuple(p for p in old.profiles if p.id != 2))
    assert diff_states(old, new) == []


def test_inbox_arrival_with_pending() -> None:
    old = base()
    later = old.inbox.latest_received_at + timedelta(minutes=5)
    new = replace(old, inbox=replace(old.inbox, latest_received_at=later, pending=5))
    assert diff_states(old, new) == [TellyboxEvent("inbox_item_arrived", None, {"pending": 5})]


def test_inbox_first_item_from_none() -> None:
    first = base().inbox
    old = replace(base(), inbox=replace(first, latest_received_at=None, pending=0))
    new = replace(old, inbox=replace(first, pending=1))
    assert diff_states(old, new) == [TellyboxEvent("inbox_item_arrived", None, {"pending": 1})]


def test_inbox_unchanged_pending_change_no_event() -> None:
    old = base()
    assert diff_states(old, replace(old, inbox=replace(old.inbox, pending=0))) == []


def test_inbox_going_back_to_none_or_earlier_no_event() -> None:
    old = base()
    assert diff_states(old, replace(old, inbox=replace(old.inbox, latest_received_at=None))) == []
    earlier = old.inbox.latest_received_at - timedelta(hours=1)
    assert diff_states(old, replace(old, inbox=replace(old.inbox, latest_received_at=earlier))) == []


def test_ordering_of_many_events_at_once() -> None:
    old = with_profile(base(), 1, can_start=True, last_five=False, watching=False, extra_s=0)
    old = with_profile(old, 2, can_start=True, last_five=False)
    old = replace(old, inbox=replace(old.inbox, latest_received_at=None))
    new = with_profile(
        old, 1, can_start=False, reason="allowance", last_five=True, watching=True, extra_s=120, blocked=True
    )
    new = with_profile(new, 2, can_start=False, reason="blocked")
    new = replace(
        new,
        tv=replace(new.tv, reachable=False),
        inbox=replace(new.inbox, latest_received_at=datetime(2026, 9, 29, 12, 0).astimezone()),
    )
    events = diff_states(old, new)
    assert kinds(events) == [
        ("time_up", 1),
        ("last_five_minutes", 1),
        ("started_watching", 1),
        ("override_applied", 1),
        ("override_applied", 1),
        ("time_up", 2),
        ("tv_unreachable", None),
        ("inbox_item_arrived", None),
    ]
    assert [e.data["override"] for e in events if e.type == "override_applied"] == ["extra_time", "blocked"]


def test_missing_optional_fields_do_not_raise() -> None:
    old = with_profile(base(), 1, extra_s=None, reason=None, can_start=None)
    assert diff_states(old, with_profile(old, 1, extra_s=None, reason=None, can_start=None)) == []
