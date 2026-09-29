"""Media player platform tests."""

from __future__ import annotations

import pytest
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import SERVICE_PLAY_MEDIA
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    Platform,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.components.media_player.errors import BrowseError

from custom_components.tellybox.const import main_device_identifier

from .conftest import INSTANCE_ID, URL
from .platform_helpers import entity_id, push_state, setup_platform


async def _setup(hass, config_entry, fake_client, control=True):
    coordinator = await setup_platform(hass, config_entry, fake_client, Platform.MEDIA_PLAYER, control=control)
    return coordinator, entity_id(hass, "media_player", "player")


async def _push(hass, coordinator, fake_client, **changes):
    fake_client.set_state(**changes)
    await push_state(hass, fake_client)
    await hass.async_block_till_done()


async def test_playing_state_and_attributes(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    state = hass.states.get(eid)
    assert eid == "media_player.tellybox"  # no name: named after the device
    assert state.state == MediaPlayerState.PLAYING
    a = state.attributes
    assert a["media_title"] == "Alongside"
    assert a["media_series_title"] == "Harbour Pups"
    assert a["media_duration"] == 660
    assert a["media_position"] == 312
    assert a["media_content_id"] == "episode:4"
    assert a["entity_picture"]
    assert a["supported_features"] & MediaPlayerEntityFeature.STOP


async def test_image_url(hass, config_entry, fake_client):
    coordinator, eid = await _setup(hass, config_entry, fake_client)
    entity = hass.data["media_player"].get_entity(eid)
    assert entity.media_image_url == f"{URL}/img/episode/4.jpg"
    assert entity.media_image_remotely_accessible is False


@pytest.mark.parametrize(
    ("np_state", "expected"),
    [
        ("playing", MediaPlayerState.PLAYING),
        ("buffering", MediaPlayerState.PLAYING),
        ("loading", MediaPlayerState.PLAYING),
        ("paused", MediaPlayerState.PAUSED),
    ],
)
async def test_state_mapping(hass, config_entry, fake_client, np_state, expected):
    coordinator, eid = await _setup(hass, config_entry, fake_client)
    await _push(hass, coordinator, fake_client, now_playing={**fake_client.state_data["now_playing"], "state": np_state})
    assert hass.states.get(eid).state == expected


async def test_idle_and_off(hass, config_entry, fake_client):
    coordinator, eid = await _setup(hass, config_entry, fake_client)
    await _push(hass, coordinator, fake_client, now_playing=None)
    state = hass.states.get(eid)
    assert state.state == MediaPlayerState.IDLE
    assert "media_title" not in state.attributes
    await _push(hass, coordinator, fake_client, tv={**fake_client.state_data["tv"], "reachable": False})
    assert hass.states.get(eid).state == MediaPlayerState.OFF


async def test_stop_only_with_control(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client, control=False)
    features = hass.states.get(eid).attributes["supported_features"]
    assert not features & MediaPlayerEntityFeature.STOP
    for f in (MediaPlayerEntityFeature.PAUSE, MediaPlayerEntityFeature.PLAY,
              MediaPlayerEntityFeature.BROWSE_MEDIA, MediaPlayerEntityFeature.PLAY_MEDIA):
        assert features & f


async def test_pause_resume_stop(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    for service in (SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_STOP):
        await hass.services.async_call(MP_DOMAIN, service, {ATTR_ENTITY_ID: eid}, blocking=True)
    assert [c[0] for c in fake_client.calls if c[0] in ("pause", "resume", "stop_now")] == [
        "pause", "resume", "stop_now"]


async def _play(hass, eid, media_id, media_type="episode"):
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_PLAY_MEDIA,
        {ATTR_ENTITY_ID: eid, ATTR_MEDIA_CONTENT_TYPE: media_type, ATTR_MEDIA_CONTENT_ID: media_id}, blocking=True,
    )


async def test_play_for_last_watchers(hass, config_entry, fake_client):
    coordinator, eid = await _setup(hass, config_entry, fake_client)
    assert coordinator.last_watchers == (1,)
    await _play(hass, eid, "episode:9")
    assert ("play", 9, [1]) in fake_client.calls


async def test_play_for_all_kids_when_no_watchers(hass, config_entry, fake_client):
    coordinator, eid = await _setup(hass, config_entry, fake_client)
    coordinator._last_watchers = ()  # nothing watched yet
    fake_client.state_data["profiles"][1]["can_start"] = True  # Noah has time again
    await _play(hass, eid, "episode:5")
    assert ("play", 5, [1, 2]) in fake_client.calls


async def test_play_bare_number(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    await _play(hass, eid, "7")
    assert ("play", 7, [1]) in fake_client.calls


async def test_play_time_up_is_translated_error(hass, config_entry, fake_client):
    coordinator, eid = await _setup(hass, config_entry, fake_client)
    coordinator._last_watchers = (2,)  # Noah is out of time
    with pytest.raises(HomeAssistantError) as err:
        await _play(hass, eid, "episode:4")
    assert err.value.translation_key == "time_up"
    assert err.value.translation_domain == "tellybox"


async def test_play_show_refused(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    with pytest.raises(HomeAssistantError):
        await _play(hass, eid, "show:2", "tvshow")
    assert not [c for c in fake_client.calls if c[0] == "play"]


async def test_browse_root_and_show(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    entity = hass.data["media_player"].get_entity(eid)
    root = await entity.async_browse_media()
    assert root.can_expand and not root.can_play
    assert [c.media_content_id for c in root.children] == ["episode:4", "show:2"]
    resume, show = root.children
    assert resume.can_play and resume.title == "Alongside"
    assert resume.thumbnail == f"{URL}/img/episode/4.jpg"
    assert show.can_expand and not show.can_play and show.thumbnail == f"{URL}/img/show/2.jpg"
    assert ("home", [1]) in fake_client.calls  # for the last watchers

    listing = await entity.async_browse_media("tvshow", "show:2")
    assert listing.title == "Harbour Pups"
    assert [c.media_content_id for c in listing.children] == ["episode:4"]
    assert listing.children[0].can_play
    assert ("show", 2) in fake_client.calls

    with pytest.raises(BrowseError):
        await entity.async_browse_media("tvshow", "show:x")


async def test_device_layout_and_unique_id(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    entry = er.async_get(hass).async_get(eid)
    assert entry.unique_id == f"{INSTANCE_ID}_player"
    device = dr.async_get(hass).async_get_device_by_identifier(main_device_identifier(INSTANCE_ID),
                                                               config_entry.entry_id)
    assert device and entry.device_id == device.id
