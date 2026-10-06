"""Helpers for the sessions in the admin state: the TV's and every browser playing in the kid app."""

from __future__ import annotations

from pytellybox import AdminState, Session

_DEVICE_PREFIX = "device:"


def device_sessions(state: AdminState) -> dict[str, Session]:
    """Active in-app sessions keyed by the browser's device id (the TV session is left out)."""
    result: dict[str, Session] = {}
    for session in state.sessions or ():
        if session.target != "device":
            continue
        device_id = session.device_id or (session.key.removeprefix(_DEVICE_PREFIX) if session.key else None)
        if device_id:
            result[device_id] = session
    return result


def session_for_profile(state: AdminState, profile_id: int) -> Session | None:
    """The first session (the TV first, as in `state.sessions`) that includes this kid.

    Tellybox puts a profile in at most one session (PB-8), so the first match is the only one.
    """
    return next((s for s in state.sessions or () if profile_id in s.profile_ids), None)
