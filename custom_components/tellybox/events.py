"""Bus events derived from state changes (plan 1).

`diff_states` compares two consecutive `AdminState`s and returns the transitions as `TellyboxEvent`s. It is pure
(no Home Assistant, no I/O). The coordinator fires each one on the bus as `tellybox_event` with the payload from
`build_payload`; device triggers (`device_trigger.py`) listen for it. The payload schema is the public contract
for automations: add optional keys only, never rename or remove one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from pytellybox import AdminState

EVENT_NAME: Final = "tellybox_event"

EVENT_TIME_UP: Final = "time_up"  # may not pick again; the episode can still run on through the grace
EVENT_LAST_FIVE: Final = "last_five_minutes"
EVENT_STARTED_WATCHING: Final = "started_watching"
EVENT_STOPPED_WATCHING: Final = "stopped_watching"
EVENT_OVERRIDE_APPLIED: Final = "override_applied"  # extras: override (extra_time|unlimited|blocked|cleared), minutes
EVENT_INBOX_ITEM: Final = "inbox_item_arrived"  # extras: pending
EVENT_TV_UNREACHABLE: Final = "tv_unreachable"
EVENT_TV_REACHABLE: Final = "tv_reachable"

PROFILE_EVENT_TYPES: Final[tuple[str, ...]] = (
    EVENT_TIME_UP,
    EVENT_LAST_FIVE,
    EVENT_STARTED_WATCHING,
    EVENT_STOPPED_WATCHING,
    EVENT_OVERRIDE_APPLIED,
)
SERVER_EVENT_TYPES: Final[tuple[str, ...]] = (EVENT_TV_UNREACHABLE, EVENT_TV_REACHABLE, EVENT_INBOX_ITEM)


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
    Never raises on a missing field. Implemented by T1."""
    raise NotImplementedError


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
