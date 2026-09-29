"""Shared fixtures: a scriptable fake Tellybox client and a config entry.

The fake stands in for `pytellybox.TellyboxClient` everywhere the integration creates one
(`custom_components.tellybox.TellyboxClient` and `custom_components.tellybox.config_flow.TellyboxClient`).
Overrides change its state the way Tellybox would and push the new state onto the event stream.
"""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytellybox import (
    AdminState,
    Home,
    Info,
    KidProfile,
    Show,
    TellyboxConnectionError,
    TellyboxForbiddenError,
    TellyboxTimeUpError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tellybox.const import CONF_CONTROL, CONF_TOKEN, CONF_URL, DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
URL = "http://tellybox.test"
TOKEN = "tbx_" + "a" * 43
INSTANCE_ID = "3f2a9c0e5b7d4e1f8a6b2c3d4e5f6a7b"


def state_dict() -> dict[str, Any]:
    """Two kids: Mila (id 1) watching with 1790 s left, Noah (id 2) out of time. Same as pytellybox's fixture."""
    return json.loads((FIXTURES / "admin_state.json").read_text())


class StreamBroken(Exception):
    """Put on the event queue to break the stream (the client raises TellyboxConnectionError)."""


class FakeTellyboxClient:
    """Implements the public interface of `pytellybox.TellyboxClient` in memory."""

    def __init__(self, base_url: str = URL, token: str | None = TOKEN, session: Any = None, **_: Any) -> None:
        self._base_url = base_url.rstrip("/")
        self.token = token
        self.state_data = state_dict()
        self.read_only = False  # overrides raise TellyboxForbiddenError
        self.fail_with: Exception | None = None  # every call raises this (e.g. TellyboxAuthError())
        self.calls: list[tuple] = []
        self.queue: asyncio.Queue = asyncio.Queue()
        self.stream_opens = 0

    # -- helpers for tests
    def set_state(self, **changes: Any) -> None:
        """Merge top-level changes and push the new state onto the stream."""
        self.state_data.update(changes)
        self.push()

    def set_profile(self, profile_id: int, **changes: Any) -> None:
        next(p for p in self.state_data["profiles"] if p["id"] == profile_id).update(changes)
        self.push()

    def push(self) -> None:
        self.queue.put_nowait(copy.deepcopy(self.state_data))

    def break_stream(self) -> None:
        self.queue.put_nowait(StreamBroken())

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def _state(self) -> AdminState:
        return AdminState.from_dict(copy.deepcopy(self.state_data))

    # -- TellyboxClient interface
    @property
    def base_url(self) -> str:
        return self._base_url

    def url(self, path: str) -> str:
        return self._base_url + path

    async def info(self) -> Info:
        self.calls.append(("info",))
        self._check()
        return Info(INSTANCE_ID, self.state_data["version"], 1, ("state", "events", "overrides", "profiles"))

    async def state(self) -> AdminState:
        self.calls.append(("state",))
        self._check()
        return self._state()

    async def events(self) -> AsyncIterator[AdminState]:
        self.stream_opens += 1
        self._check()
        yield self._state()
        while True:
            item = await self.queue.get()
            if isinstance(item, BaseException):
                raise TellyboxConnectionError("stream broken") from item
            yield AdminState.from_dict(item)

    def _targets(self, profile_ids: Sequence[int] | None) -> list[dict]:
        return [p for p in self.state_data["profiles"] if profile_ids is None or p["id"] in profile_ids]

    async def _override(self, name: str, profile_ids: Sequence[int] | None, change) -> AdminState:
        self.calls.append((name, None if profile_ids is None else list(profile_ids)))
        self._check()
        if self.read_only:
            raise TellyboxForbiddenError("forbidden")
        for p in self._targets(profile_ids):
            change(p)
        self.push()
        return self._state()

    async def add_time(self, minutes: int, profile_ids: Sequence[int] | None = None) -> AdminState:
        self.calls.append(("add_time", minutes))

        def change(p: dict) -> None:
            p["extra_s"] = (p["extra_s"] or 0) + minutes * 60
            if p["remaining_s"] is not None:
                p["remaining_s"] += minutes * 60
            p["can_start"], p["reason"] = True, None

        return await self._override("add_time_targets", profile_ids, change)

    async def set_unlimited(self, profile_ids: Sequence[int] | None = None) -> AdminState:
        return await self._override("set_unlimited", profile_ids,
                                    lambda p: p.update(unlimited=True, remaining_s=None, can_start=True))

    async def block(self, profile_ids: Sequence[int] | None = None) -> AdminState:
        return await self._override("block", profile_ids,
                                    lambda p: p.update(blocked=True, can_start=False, reason="blocked"))

    async def clear_today(self, profile_ids: Sequence[int] | None = None) -> AdminState:
        return await self._override("clear_today", profile_ids, lambda p: p.update(blocked=False, unlimited=False))

    async def stop_now(self) -> AdminState:
        self.calls.append(("stop_now",))
        self._check()
        if self.read_only:
            raise TellyboxForbiddenError("forbidden")
        self.state_data["now_playing"] = None
        self.push()
        return self._state()

    async def kid_profiles(self) -> list[KidProfile]:
        self.calls.append(("kid_profiles",))
        return [KidProfile(p["id"], p["name"], None, p["avatar"]) for p in self.state_data["profiles"]]

    async def home(self, profile_ids: Sequence[int] | None = None) -> Home:
        self.calls.append(("home", None if profile_ids is None else list(profile_ids)))
        return Home.from_dict({
            "continue": [{"episode_id": 4, "show_id": 2, "thumb": "/img/episode/4.jpg", "title": "Alongside",
                          "progress": 0.4, "finished": False, "kind": "resume"}],
            "shows": [{"show_id": 2, "artwork": "/img/show/2.jpg", "title": "Harbour Pups"}],
        })

    async def show(self, show_id: int, profile_ids: Sequence[int] | None = None) -> Show:
        self.calls.append(("show", show_id))
        return Show.from_dict({"show_id": show_id, "artwork": f"/img/show/{show_id}.jpg", "title": "Harbour Pups",
                               "episodes": [{"episode_id": 4, "show_id": show_id, "thumb": "/img/episode/4.jpg",
                                             "title": "Alongside", "progress": None, "finished": False}]})

    async def play(self, episode_id: int, profile_ids: Sequence[int]) -> None:
        self.calls.append(("play", episode_id, list(profile_ids)))
        self._check()
        if any(p["can_start"] is False for p in self._targets(profile_ids)):
            raise TellyboxTimeUpError("time_up")

    async def pause(self) -> None:
        self.calls.append(("pause",))
        self._check()

    async def resume(self) -> None:
        self.calls.append(("resume",))
        self._check()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def fake_client() -> FakeTellyboxClient:
    return FakeTellyboxClient()


@pytest.fixture
def patch_client(fake_client):
    """Every client the integration creates is `fake_client`."""
    factory = lambda *a, **kw: fake_client  # noqa: E731
    with (
        patch("custom_components.tellybox.TellyboxClient", side_effect=factory),
        patch("custom_components.tellybox.config_flow.TellyboxClient", side_effect=factory),
    ):
        yield fake_client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, title="Tellybox", unique_id=INSTANCE_ID,
        data={CONF_URL: URL, CONF_TOKEN: TOKEN}, options={CONF_CONTROL: True},
    )


@pytest.fixture
async def setup_integration(hass, config_entry, patch_client):
    """The integration set up against the fake client; returns the fake."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return patch_client
