"""The per-kid media player: state from sessions, read-only attributes, play and browse for one kid."""

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
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.tellybox.const import profile_device_identifier
from custom_components.tellybox.media_player import PLAYER, TellyboxKidMediaPlayer

from .conftest import INSTANCE_ID, URL
from .platform_helpers import entity_id, push_state, setup_platform

BLOCKED = (MediaPlayerEntityFeature.PAUSE, MediaPlayerEntityFeature.PLAY, MediaPlayerEntityFeature.STOP)


async def _setup(hass, config_entry, fake_client, control=True):
    coordinator = await setup_platform(hass, config_entry, fake_client, Platform.MEDIA_PLAYER, control=control)
    return coordinator, entity_id(hass, "media_player", "player", 1)


async def _push(hass, fake_client, **changes):
    fake_client.set_state(**changes)
    await push_state(hass, fake_client)
    await hass.async_block_till_done()


def _tv_session(fake_client, **changes):
    return [{**fake_client.state_data["sessions"][0], **changes}]


def _app_session(**changes):
    return {"key": "device:abc", "target": "device", "label": "iPhone Safari", "device_id": "abc",
            "episode_id": 7, "show_id": 2, "title": "Low Tide", "state": "playing", "position_s": 10,
            "duration_s": 300, "profile_ids": [2], **changes}


async def test_entity_and_unique_id_on_the_kid_device(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    assert eid == "media_player.mila"
    entry = er.async_get(hass).async_get(eid)
    assert entry.unique_id == f"{INSTANCE_ID}_profile_1_player"
    device = dr.async_get(hass).async_get_device_by_identifier(profile_device_identifier(INSTANCE_ID, 1),
                                                               config_entry.entry_id)
    assert device and entry.device_id == device.id
    noah = entity_id(hass, "media_player", "player", 2)
    assert noah == "media_player.noah"


async def test_playing_on_the_tv(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    state = hass.states.get(eid)
    assert state.state == MediaPlayerState.PLAYING
    a = state.attributes
    assert a["media_title"] == "Alongside"
    assert a["media_duration"] == 660
    assert a["media_position"] == 312
    assert a["media_content_id"] == "episode:4"
    assert a["watching_on"] == "TV"
    assert "media_series_title" not in a  # sessions carry no show title
    assert a["entity_picture"]
    assert hass.states.get(entity_id(hass, "media_player", "player", 2)).state == MediaPlayerState.IDLE


async def test_artwork_url(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    entity = hass.data["media_player"].get_entity(eid)
    assert entity.media_image_url == f"{URL}/img/episode/4.jpg"
    assert entity.media_image_remotely_accessible is False


@pytest.mark.parametrize(
    ("session_state", "expected"),
    [
        ("playing", MediaPlayerState.PLAYING),
        ("buffering", MediaPlayerState.PLAYING),
        ("loading", MediaPlayerState.PLAYING),
        ("paused", MediaPlayerState.PAUSED),
    ],
)
async def test_state_mapping(hass, config_entry, fake_client, session_state, expected):
    _, eid = await _setup(hass, config_entry, fake_client)
    await _push(hass, fake_client, sessions=_tv_session(fake_client, state=session_state))
    assert hass.states.get(eid).state == expected


async def test_idle_and_off(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    await _push(hass, fake_client, sessions=[], now_playing=None)
    state = hass.states.get(eid)
    assert state.state == MediaPlayerState.IDLE
    assert "media_title" not in state.attributes
    assert "watching_on" not in state.attributes
    await _push(hass, fake_client, tv={**fake_client.state_data["tv"], "reachable": False})
    assert hass.states.get(eid).state == MediaPlayerState.OFF


async def test_in_app_session_is_read_only_with_watching_on(hass, config_entry, fake_client):
    _, _ = await _setup(hass, config_entry, fake_client)
    noah = entity_id(hass, "media_player", "player", 2)
    await _push(hass, fake_client, sessions=[*fake_client.state_data["sessions"], _app_session()])
    state = hass.states.get(noah)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes["watching_on"] == "iPhone Safari"
    assert state.attributes["media_title"] == "Low Tide"
    assert state.attributes["media_content_id"] == "episode:7"
    # An unreachable TV doesn't turn off a kid who watches in the app.
    await _push(hass, fake_client, tv={**fake_client.state_data["tv"], "reachable": False})
    assert hass.states.get(noah).state == MediaPlayerState.PLAYING


async def test_now_playing_fallback_without_sessions(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    await _push(hass, fake_client, sessions=[])
    state = hass.states.get(eid)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes["media_title"] == "Alongside"
    assert state.attributes["media_series_title"] == "Harbour Pups"
    assert state.attributes["media_content_id"] == "episode:4"
    assert "watching_on" not in state.attributes
    assert hass.states.get(entity_id(hass, "media_player", "player", 2)).state == MediaPlayerState.IDLE


@pytest.mark.parametrize("control", [True, False])
async def test_features_are_browse_and_play_only(hass, config_entry, fake_client, control):
    _, eid = await _setup(hass, config_entry, fake_client, control=control)
    features = hass.states.get(eid).attributes["supported_features"]
    assert features == MediaPlayerEntityFeature.BROWSE_MEDIA | MediaPlayerEntityFeature.PLAY_MEDIA
    for f in BLOCKED:
        assert not features & f


async def _play(hass, eid, media_id, media_type="episode"):
    await hass.services.async_call(
        MP_DOMAIN, SERVICE_PLAY_MEDIA,
        {ATTR_ENTITY_ID: eid, ATTR_MEDIA_CONTENT_TYPE: media_type, ATTR_MEDIA_CONTENT_ID: media_id}, blocking=True,
    )


async def test_play_is_for_this_kid_only(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    await _play(hass, eid, "episode:9")
    assert [c for c in fake_client.calls if c[0] == "play"] == [("play", 9, [1])]
    assert not [c for c in fake_client.calls if c[0] in ("pause", "resume", "stop_now")]


async def test_play_show_refused(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    with pytest.raises(HomeAssistantError):
        await _play(hass, eid, "show:2", "tvshow")
    assert not [c for c in fake_client.calls if c[0] == "play"]


async def test_play_time_up_is_translated_error(hass, config_entry, fake_client):
    _, _ = await _setup(hass, config_entry, fake_client)
    noah = entity_id(hass, "media_player", "player", 2)  # can_start is False
    with pytest.raises(HomeAssistantError) as err:
        await _play(hass, noah, "episode:4")
    assert err.value.translation_key == "time_up"
    assert err.value.translation_domain == "tellybox"
    assert [c for c in fake_client.calls if c[0] == "play"] == [("play", 4, [2])]  # asked, refused
    assert hass.states.get(noah).state == MediaPlayerState.IDLE  # nothing started


async def test_browse_is_scoped_to_the_kid(hass, config_entry, fake_client):
    _, eid = await _setup(hass, config_entry, fake_client)
    entity = hass.data["media_player"].get_entity(eid)
    root = await entity.async_browse_media()
    assert root.title == "Mila"
    assert [c.media_content_id for c in root.children] == ["episode:4", "show:2"]
    assert ("home", [1]) in fake_client.calls
    listing = await entity.async_browse_media("tvshow", "show:2")
    assert listing.title == "Harbour Pups"
    assert ("show", 2) in fake_client.calls


async def test_browse_passes_kid_ids_to_the_client(hass, config_entry, fake_client):
    _, _ = await _setup(hass, config_entry, fake_client)
    seen = []
    orig_show = fake_client.show

    async def show(show_id, profile_ids=None):
        seen.append(("show", show_id, list(profile_ids)))
        return await orig_show(show_id, profile_ids)

    fake_client.show = show
    entity = hass.data["media_player"].get_entity(entity_id(hass, "media_player", "player", 2))
    root = await entity.async_browse_media()
    assert root.title == "Noah"
    await entity.async_browse_media("tvshow", "show:2")
    assert ("home", [2]) in fake_client.calls
    assert seen == [("show", 2, [2])]


async def test_a_kid_appearing_later_gets_a_player(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("media_player", "tellybox", f"{INSTANCE_ID}_profile_3_player") is None
    new = {**fake_client.state_data["profiles"][1], "id": 3, "name": "Lena", "can_start": True, "reason": None}
    await _push(hass, fake_client, profiles=[*fake_client.state_data["profiles"], new])
    eid = entity_id(hass, "media_player", "player", 3)
    assert eid == "media_player.lena"
    assert hass.states.get(eid).state == MediaPlayerState.IDLE


async def test_unavailable_while_the_kid_is_missing(hass, config_entry, fake_client):
    coordinator, _ = await _setup(hass, config_entry, fake_client)
    entity = TellyboxKidMediaPlayer(coordinator, PLAYER, 1)
    assert entity.available
    gone = TellyboxKidMediaPlayer(coordinator, PLAYER, 99)  # not in the state (a deleted kid)
    assert not gone.available
