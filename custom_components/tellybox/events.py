"""Bus events derived from state changes (plan 1).

`diff_states` compares two consecutive `AdminState`s and returns the transitions as `TellyboxEvent`s. It is pure
(no Home Assistant, no I/O). The coordinator fires each one on the bus as `tellybox_event` with the payload from
`build_payload`; device triggers (`device_trigger.py`) listen for it. The payload schema is the public contract
for automations: add optional keys only, never rename or remove one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from pytellybox import AdminState, ServerEvent

EVENT_NAME: Final = "tellybox_event"

EVENT_TIME_UP: Final = "time_up"  # may not pick again; the episode can still run on through the grace
EVENT_LAST_FIVE: Final = "last_five_minutes"
EVENT_STARTED_WATCHING: Final = "started_watching"
EVENT_STOPPED_WATCHING: Final = "stopped_watching"
EVENT_OVERRIDE_APPLIED: Final = "override_applied"  # extras: override (extra_time|unlimited|blocked|cleared), minutes
EVENT_INBOX_ITEM: Final = "inbox_item_arrived"  # extras: pending
EVENT_DOWNLOAD_READY: Final = "download_ready"  # extras: held_ready, new_ready (typed events only)
EVENT_TV_UNREACHABLE: Final = "tv_unreachable"
EVENT_TV_REACHABLE: Final = "tv_reachable"

PROFILE_EVENT_TYPES: Final[tuple[str, ...]] = (
    EVENT_TIME_UP,
    EVENT_LAST_FIVE,
    EVENT_STARTED_WATCHING,
    EVENT_STOPPED_WATCHING,
    EVENT_OVERRIDE_APPLIED,
)
SERVER_EVENT_TYPES: Final[tuple[str, ...]] = (
    EVENT_TV_UNREACHABLE,
    EVENT_TV_REACHABLE,
    EVENT_INBOX_ITEM,
    EVENT_DOWNLOAD_READY,
)


@dataclass(frozen=True, slots=True)
class TellyboxEvent:
    """One transition. `profile_id` is None for server-level events; `data` holds the type-specific extras only
    (`reason` for time_up, `override`/`minutes` for override_applied, `pending` for inbox_item_arrived)."""

    type: str
    profile_id: int | None
    data: dict[str, Any]


def diff_states(old: AdminState, new: AdminState) -> list[TellyboxEvent]:
    """The transitions from `old` to `new`, in a stable order: per kid in `new.profiles` order (time_up,
    last_five_minutes, started_watching, stopped_watching, override_applied), then the server events
    (tv_unreachable/tv_reachable, inbox_item_arrived). A kid in `new` but not in `old` yields nothing (baseline).
    Never raises on a missing field."""
    events: list[TellyboxEvent] = []
    old_profiles = {p.id: p for p in getattr(old, "profiles", None) or ()}
    day_changed = _day(old) != _day(new)
    for profile in getattr(new, "profiles", None) or ():
        before = old_profiles.get(profile.id)
        if before is not None:
            events.extend(_profile_events(before, profile, day_changed))
    events.extend(_server_events(old, new))
    return events


def _day(state: AdminState) -> Any:
    return getattr(getattr(state, "day", None), "date", None)


def _time_up(profile: Any) -> bool:
    return getattr(profile, "can_start", None) is False


def _profile_events(old: Any, new: Any, day_changed: bool) -> list[TellyboxEvent]:
    pid = new.id
    events: list[TellyboxEvent] = []
    if not _time_up(old) and _time_up(new):
        events.append(TellyboxEvent(EVENT_TIME_UP, pid, {"reason": getattr(new, "reason", None)}))
    if not getattr(old, "last_five", False) and getattr(new, "last_five", False):
        events.append(TellyboxEvent(EVENT_LAST_FIVE, pid, {}))
    was, now = bool(getattr(old, "watching", False)), bool(getattr(new, "watching", False))
    if not was and now:
        events.append(TellyboxEvent(EVENT_STARTED_WATCHING, pid, {}))
    if was and not now:
        events.append(TellyboxEvent(EVENT_STOPPED_WATCHING, pid, {}))

    def override(kind: str, **extra: Any) -> None:
        events.append(TellyboxEvent(EVENT_OVERRIDE_APPLIED, pid, {"override": kind, **extra}))

    old_extra, new_extra = getattr(old, "extra_s", None) or 0, getattr(new, "extra_s", None) or 0
    minutes = (new_extra - old_extra) // 60
    if minutes >= 1:  # a decrease is the daily reset; under a minute is not something Tellybox does
        override("extra_time", minutes=minutes)
    old_unl, new_unl = bool(getattr(old, "unlimited", False)), bool(getattr(new, "unlimited", False))
    old_blk, new_blk = bool(getattr(old, "blocked", False)), bool(getattr(new, "blocked", False))
    if not old_unl and new_unl:
        override("unlimited")
    if not old_blk and new_blk:
        override("blocked")
    if ((old_unl and not new_unl) or (old_blk and not new_blk)) and not day_changed:
        override("cleared")
    return events


def _server_events(old: AdminState, new: AdminState) -> list[TellyboxEvent]:
    events: list[TellyboxEvent] = []
    old_tv, new_tv = getattr(old, "tv", None), getattr(new, "tv", None)
    if old_tv is not None and new_tv is not None:
        was, now = bool(getattr(old_tv, "reachable", False)), bool(getattr(new_tv, "reachable", False))
        if was and not now:
            events.append(TellyboxEvent(EVENT_TV_UNREACHABLE, None, {}))
        elif now and not was:
            events.append(TellyboxEvent(EVENT_TV_REACHABLE, None, {}))
    old_inbox, new_inbox = getattr(old, "inbox", None), getattr(new, "inbox", None)
    old_at, new_at = getattr(old_inbox, "latest_received_at", None), getattr(new_inbox, "latest_received_at", None)
    if new_at is not None and _later(new_at, old_at):
        events.append(TellyboxEvent(EVENT_INBOX_ITEM, None, {"pending": getattr(new_inbox, "pending", 0)}))
    return events


def _later(new_at: Any, old_at: Any) -> bool:
    if old_at is None:
        return True
    try:
        return bool(new_at > old_at)
    except TypeError:  # naive vs aware: fall back to "changed"
        return bool(new_at != old_at)


_PLAYBACK_KEYS: Final = ("episode_id", "show_id", "title", "show", "target", "label")
_OVERRIDE_NAMES: Final = {
    "extra_minutes": "extra_time",
    "unlimited": "unlimited",
    "block": "blocked",
    "clear": "cleared",
    "stop_now": "stop_now",
}


def from_server_event(event: ServerEvent) -> list[TellyboxEvent]:
    """Map a typed server event to `TellyboxEvent`s: one per kid in `profile_ids` for per-kid types, one
    server-level event (profile_id None) for the others. An unknown type passes through as a server-level event
    carrying the event's data, so new server events work without a release here. Never raises."""
    data = dict(event.data)
    kind = event.type

    def per_kid(type_: str, extra: dict[str, Any]) -> list[TellyboxEvent]:
        return [TellyboxEvent(type_, pid, dict(extra)) for pid in event.profile_ids]

    def playback() -> dict[str, Any]:
        return {key: data.get(key) for key in _PLAYBACK_KEYS}

    if kind == "time_up":
        return per_kid(EVENT_TIME_UP, {"reason": data.get("reason")})
    if kind == "last_five":
        return per_kid(EVENT_LAST_FIVE, {"remaining_s": data.get("remaining_s")})
    if kind == "playback_started":
        return per_kid(EVENT_STARTED_WATCHING, playback())
    if kind == "playback_stopped":
        return per_kid(
            EVENT_STOPPED_WATCHING, {"reason": data.get("reason"), "position_s": data.get("position_s"), **playback()}
        )
    if kind == "override_applied":
        what = data.get("kind")
        extra: dict[str, Any] = {"override": _OVERRIDE_NAMES.get(what, what) if isinstance(what, str) else what}
        if what == "extra_minutes":
            extra["minutes"] = data.get("value")
        extra["source"] = data.get("source") if isinstance(data.get("source"), str) else None
        return per_kid(EVENT_OVERRIDE_APPLIED, extra)
    if kind == "inbox_item_arrived":
        return [TellyboxEvent(EVENT_INBOX_ITEM, None, {"pending": data.get("pending"), "new_items": data.get("new_items")})]
    if kind == "download_ready":
        return [TellyboxEvent(EVENT_DOWNLOAD_READY, None, {"held_ready": data.get("held_ready"), "new_ready": data.get("new_ready")})]
    if not kind:
        return []
    return [TellyboxEvent(kind, None, data)]


def build_payload(
    event: TellyboxEvent, *, instance_id: str, device_id: str, profile_name: str | None = None
) -> dict[str, Any]:
    """The bus event data: `{"type", "device_id", "instance_id", "profile_id"?, "profile_name"?, **data}`.
    `device_id` is the device-registry id of the device the event is about. The keys `type`, `device_id`,
    `instance_id`, `profile_id` and `profile_name` always win over a clashing key in `event.data`. Plan 13's
    server events reuse this builder, so keep it free of Home Assistant imports."""
    payload: dict[str, Any] = dict(event.data)
    payload.update(type=event.type, device_id=device_id, instance_id=instance_id)
    if event.profile_id is not None:
        payload["profile_id"] = event.profile_id
        if profile_name is not None:
            payload["profile_name"] = profile_name
    return payload
