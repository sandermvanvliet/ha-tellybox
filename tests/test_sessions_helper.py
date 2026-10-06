"""Tests for the sessions helper module."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pytellybox import AdminState, Session

from custom_components.tellybox.sessions import device_sessions, session_for_profile


@pytest.fixture
def base_state_dict() -> dict:
    """A minimal admin state dict for testing."""
    return {
        "instance_id": "test-instance",
        "version": "1.0.0",
        "api": 1,
        "day": {"date": "2026-10-06", "resets_at": "2026-10-07T02:00:00+00:00"},
        "tv": {"connection": "CONNECTED", "reachable": True, "device": "TV"},
        "profiles": [
            {"id": 1, "name": "Alice", "avatar": "fox", "allowance_s": 3600, "extra_s": 0, "used_s": 1800,
             "remaining_s": 1800, "unlimited": False, "blocked": False, "mode": "ignore_pauses",
             "max_session_s": 5400, "session_elapsed_s": 1200, "can_start": True, "reason": None,
             "watching": True, "last_five": False, "allowance_source": "inherit", "max_session_source": "custom",
             "visible_shows": 1},
            {"id": 2, "name": "Bob", "avatar": None, "allowance_s": 3600, "extra_s": 0, "used_s": 1800,
             "remaining_s": 1800, "unlimited": False, "blocked": False, "mode": "ignore_pauses",
             "max_session_s": 5400, "session_elapsed_s": None, "can_start": True, "reason": None,
             "watching": False, "last_five": False, "allowance_source": "inherit", "max_session_source": "custom",
             "visible_shows": 1},
        ],
        "group": {"remaining_s": 1800, "time_up": False, "last_five": False, "action": "continue",
                  "reason": None, "grace_ends_at": None, "session_started_at": "2026-10-06T13:10:00+00:00",
                  "session_elapsed_s": 1200},
        "jobs": {"queued": 0, "running": 0, "failed": 0, "held_ready": 0},
        "disk": {"media_bytes": 1000000, "free_bytes": 10000000},
        "sessions": [],
    }


def _make_tv_session() -> dict:
    """Create a TV session dict."""
    return {
        "key": "tv",
        "target": "tv",
        "label": "TV",
        "device_id": None,
        "episode_id": 10,
        "show_id": 1,
        "title": "Episode 1",
        "state": "playing",
        "position_s": 100,
        "duration_s": 1200,
        "profile_ids": [1],
    }


def _make_device_session(device_id: str, profile_ids: list[int], label: str = "iPhone Safari") -> dict:
    """Create a device session dict."""
    return {
        "key": f"device:{device_id}",
        "target": "device",
        "label": label,
        "device_id": device_id,
        "episode_id": 20,
        "show_id": 2,
        "title": "Episode 2",
        "state": "paused",
        "position_s": 50,
        "duration_s": 1200,
        "profile_ids": profile_ids,
    }


class TestDeviceSessions:
    """Tests for device_sessions function."""

    async def test_empty_sessions(self, base_state_dict):
        """Empty sessions returns empty dict."""
        state = AdminState.from_dict(base_state_dict)
        result = device_sessions(state)
        assert result == {}

    async def test_none_sessions(self, base_state_dict):
        """Missing sessions (None) returns empty dict."""
        state_dict = base_state_dict
        state_dict["sessions"] = None
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert result == {}

    async def test_excludes_tv_session(self, base_state_dict):
        """TV session is excluded."""
        state_dict = base_state_dict
        state_dict["sessions"] = [_make_tv_session()]
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert result == {}

    async def test_single_device_session(self, base_state_dict):
        """Single device session is returned with its device id as key."""
        state_dict = base_state_dict
        device_session = _make_device_session("abc123", [1])
        state_dict["sessions"] = [device_session]
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert len(result) == 1
        assert "abc123" in result
        assert result["abc123"].label == "iPhone Safari"
        assert result["abc123"].profile_ids == (1,)

    async def test_multiple_device_sessions(self, base_state_dict):
        """Multiple device sessions are all returned."""
        state_dict = base_state_dict
        session1 = _make_device_session("abc123", [1])
        session2 = _make_device_session("def456", [2], "iPad Safari")
        state_dict["sessions"] = [session1, session2]
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert len(result) == 2
        assert "abc123" in result
        assert "def456" in result
        assert result["abc123"].label == "iPhone Safari"
        assert result["def456"].label == "iPad Safari"

    async def test_tv_and_device_sessions_tv_excluded(self, base_state_dict):
        """TV session is excluded even when device sessions are present."""
        state_dict = base_state_dict
        tv_session = _make_tv_session()
        device_session = _make_device_session("abc123", [1])
        state_dict["sessions"] = [tv_session, device_session]
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert len(result) == 1
        assert "abc123" in result
        assert result["abc123"].target == "device"

    async def test_device_id_from_key_parsing(self, base_state_dict):
        """Device id is extracted from key when device_id field is present."""
        state_dict = base_state_dict
        device_session = _make_device_session("xyz789", [1])
        state_dict["sessions"] = [device_session]
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert "xyz789" in result

    async def test_group_session_with_multiple_kids(self, base_state_dict):
        """Group session with multiple kids is returned."""
        state_dict = base_state_dict
        group_session = _make_device_session("abc123", [1, 2])
        state_dict["sessions"] = [group_session]
        state = AdminState.from_dict(state_dict)
        result = device_sessions(state)
        assert len(result) == 1
        assert "abc123" in result
        assert result["abc123"].profile_ids == (1, 2)


class TestSessionForProfile:
    """Tests for session_for_profile function."""

    async def test_empty_sessions(self, base_state_dict):
        """Empty sessions returns None."""
        state = AdminState.from_dict(base_state_dict)
        result = session_for_profile(state, 1)
        assert result is None

    async def test_none_sessions(self, base_state_dict):
        """Missing sessions (None) returns None."""
        state_dict = base_state_dict
        state_dict["sessions"] = None
        state = AdminState.from_dict(state_dict)
        result = session_for_profile(state, 1)
        assert result is None

    async def test_tv_session_found_for_kid(self, base_state_dict):
        """TV session is found for a kid in it."""
        state_dict = base_state_dict
        tv_session = _make_tv_session()
        state_dict["sessions"] = [tv_session]
        state = AdminState.from_dict(state_dict)
        result = session_for_profile(state, 1)
        assert result is not None
        assert result.target == "tv"
        assert result.label == "TV"

    async def test_device_session_found_for_kid(self, base_state_dict):
        """Device session is found for a kid in it."""
        state_dict = base_state_dict
        device_session = _make_device_session("abc123", [2])
        state_dict["sessions"] = [device_session]
        state = AdminState.from_dict(state_dict)
        result = session_for_profile(state, 2)
        assert result is not None
        assert result.target == "device"
        assert result.device_id == "abc123"

    async def test_group_session_found_for_each_kid(self, base_state_dict):
        """Group session is found for each kid in it."""
        state_dict = base_state_dict
        group_session = _make_device_session("abc123", [1, 2])
        state_dict["sessions"] = [group_session]
        state = AdminState.from_dict(state_dict)

        result1 = session_for_profile(state, 1)
        assert result1 is not None
        assert result1.device_id == "abc123"
        assert 1 in result1.profile_ids

        result2 = session_for_profile(state, 2)
        assert result2 is not None
        assert result2.device_id == "abc123"
        assert 2 in result2.profile_ids

    async def test_tv_wins_over_device_session_for_same_kid(self, base_state_dict):
        """When both TV and device sessions contain a kid, TV is returned (first in state.sessions)."""
        state_dict = base_state_dict
        tv_session = _make_tv_session()
        device_session = _make_device_session("abc123", [1])
        state_dict["sessions"] = [tv_session, device_session]
        state = AdminState.from_dict(state_dict)

        result = session_for_profile(state, 1)
        assert result is not None
        assert result.target == "tv"
        assert result.key == "tv"

    async def test_unknown_profile_returns_none(self, base_state_dict):
        """Unknown profile id returns None."""
        state_dict = base_state_dict
        tv_session = _make_tv_session()
        state_dict["sessions"] = [tv_session]
        state = AdminState.from_dict(state_dict)

        result = session_for_profile(state, 999)
        assert result is None

    async def test_first_match_when_multiple_device_sessions(self, base_state_dict):
        """Returns first matching session when multiple device sessions exist."""
        state_dict = base_state_dict
        device_session1 = _make_device_session("abc123", [1])
        device_session2 = _make_device_session("def456", [2])
        state_dict["sessions"] = [device_session1, device_session2]
        state = AdminState.from_dict(state_dict)

        result = session_for_profile(state, 1)
        assert result is not None
        assert result.device_id == "abc123"

    async def test_kid_not_in_first_session_but_in_second(self, base_state_dict):
        """Kid not in first session but in second is found in second."""
        state_dict = base_state_dict
        device_session1 = _make_device_session("abc123", [1])
        device_session2 = _make_device_session("def456", [2])
        state_dict["sessions"] = [device_session1, device_session2]
        state = AdminState.from_dict(state_dict)

        result = session_for_profile(state, 2)
        assert result is not None
        assert result.device_id == "def456"

    async def test_profile_id_3_not_in_any_session(self, base_state_dict):
        """Profile id not in any session returns None (even if profile exists)."""
        state_dict = base_state_dict
        # Add a 3rd profile to the state
        state_dict["profiles"].append({
            "id": 3, "name": "Charlie", "avatar": None, "allowance_s": 3600, "extra_s": 0,
            "used_s": 1800, "remaining_s": 1800, "unlimited": False, "blocked": False,
            "mode": "ignore_pauses", "max_session_s": 5400, "session_elapsed_s": None,
            "can_start": True, "reason": None, "watching": False, "last_five": False,
            "allowance_source": "inherit", "max_session_source": "custom", "visible_shows": 1
        })
        device_session = _make_device_session("abc123", [1, 2])
        state_dict["sessions"] = [device_session]
        state = AdminState.from_dict(state_dict)

        result = session_for_profile(state, 3)
        assert result is None
