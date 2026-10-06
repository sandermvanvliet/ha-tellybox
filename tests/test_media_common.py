"""Shared media helper tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.exceptions import HomeAssistantError

from custom_components.tellybox.media_common import parse_media_id, play_for


@pytest.mark.parametrize(
    ("media_id", "expected"),
    [("show:2", ("show", 2)), ("episode:4", ("episode", 4)), ("7", ("episode", 7))],
)
def test_parse(media_id, expected):
    assert parse_media_id(media_id) == expected


@pytest.mark.parametrize("media_id", ["garbage", "show:x", "", "episode:"])
def test_parse_garbage(media_id):
    with pytest.raises(BrowseError):
        parse_media_id(media_id)


def _coordinator():
    coordinator = MagicMock()
    coordinator.client.play = AsyncMock()

    async def run(command):
        return await command()

    coordinator.async_command = AsyncMock(side_effect=run)
    return coordinator


async def test_play_for_refuses_show():
    coordinator = _coordinator()
    with pytest.raises(HomeAssistantError) as err:
        await play_for(coordinator, "show:2", [1])
    assert err.value.translation_key == "request"
    coordinator.client.play.assert_not_called()


async def test_play_for_no_kids():
    coordinator = _coordinator()
    with pytest.raises(HomeAssistantError) as err:
        await play_for(coordinator, "episode:4", [])
    assert err.value.translation_key == "no_kids"
    coordinator.client.play.assert_not_called()


async def test_play_for_plays_for_given_kids():
    coordinator = _coordinator()
    await play_for(coordinator, "episode:4", [1, 2])
    coordinator.client.play.assert_awaited_once_with(4, [1, 2])
    await play_for(coordinator, "9", [2])
    coordinator.client.play.assert_awaited_with(9, [2])
