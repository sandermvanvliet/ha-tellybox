"""Image platform tests: each kid's photo or avatar, cached and served through Home Assistant."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytellybox import Image, TellyboxConnectionError

from custom_components.tellybox.const import DOMAIN, profile_device_identifier

from .conftest import INSTANCE_ID, TINY_JPEG, TINY_SVG
from .platform_helpers import entity_id, push_state, setup_platform, uid


async def _setup(hass, config_entry, fake_client):
    return await setup_platform(hass, config_entry, fake_client, Platform.IMAGE)


def _eid(hass, profile_id=1):
    return entity_id(hass, "image", "picture", profile_id)


async def _body(hass, hass_client, profile_id=1):
    eid = _eid(hass, profile_id)
    token = hass.states.get(eid).attributes["access_token"]
    client = await hass_client()
    return await client.get(f"/api/image_proxy/{eid}?token={token}")


async def test_entity_per_kid_with_unique_id_and_device(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    registry = er.async_get(hass)
    for pid in (1, 2):
        entry = registry.async_get(_eid(hass, pid))
        assert entry.unique_id == uid("picture", pid)
        assert entry.entity_category is None
        assert entry.disabled_by is None
        device = dr.async_get(hass).async_get(entry.device_id)
        assert device.identifiers == {profile_device_identifier(INSTANCE_ID, pid)}
    assert _eid(hass, 1).endswith("_picture")


async def test_photo_preferred_over_avatar(hass, hass_client, config_entry, fake_client):
    fake_client.set_profile(1, picture="/img/profile/1.jpg")
    await _setup(hass, config_entry, fake_client)
    assert fake_client.image_paths == ["/img/profile/1.jpg"]
    resp = await _body(hass, hass_client)
    assert resp.status == 200
    assert resp.content_type == "image/jpeg"
    assert await resp.read() == TINY_JPEG


async def test_avatar_fallback(hass, hass_client, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)  # Mila: no photo, avatar "fox"
    assert fake_client.image_paths == ["/static/avatars/fox.svg"]
    resp = await _body(hass, hass_client)
    assert resp.status == 200
    assert resp.content_type == "image/svg+xml"
    assert await resp.read() == TINY_SVG


async def test_neither_picture_nor_avatar_is_unavailable(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)  # Noah: no avatar, no photo
    assert hass.states.get(_eid(hass, 2)).state == STATE_UNAVAILABLE
    assert hass.states.get(_eid(hass, 1)).state != STATE_UNAVAILABLE
    assert all("2" not in p for p in fake_client.image_paths)


async def test_new_kid_adds_entity(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    fake_client.state_data["profiles"].append(
        {**fake_client.state_data["profiles"][0], "id": 3, "name": "Sam", "avatar": "owl"})
    await push_state(hass, fake_client)
    assert hass.states.get(_eid(hass, 3)) is not None
    assert "/static/avatars/owl.svg" in fake_client.image_paths


async def test_no_refetch_on_repeated_updates(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    before = list(fake_client.image_paths)
    for _ in range(3):
        await push_state(hass, fake_client)
    assert fake_client.image_paths == before


async def test_refetch_when_picture_path_changes(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    fake_client.set_profile(1, picture="/img/profile/1.jpg")
    await hass.async_block_till_done()
    assert fake_client.image_paths == ["/static/avatars/fox.svg", "/img/profile/1.jpg"]


async def test_refetch_after_an_hour_and_last_updated(hass, config_entry, fake_client, freezer):
    await _setup(hass, config_entry, fake_client)
    eid = _eid(hass)
    first = hass.states.get(eid).state
    assert first != STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=59))
    await push_state(hass, fake_client)
    assert len(fake_client.image_paths) == 1  # not yet an hour

    freezer.tick(timedelta(minutes=2))
    await push_state(hass, fake_client)
    assert fake_client.image_paths.count("/static/avatars/fox.svg") == 2
    assert hass.states.get(eid).state == first  # identical bytes: image_last_updated did not move

    fake_client.images["/static/avatars/fox.svg"] = Image(b"<svg>other</svg>", "image/svg+xml")
    freezer.tick(timedelta(hours=1, minutes=1))
    await push_state(hass, fake_client)
    assert fake_client.image_paths.count("/static/avatars/fox.svg") == 3
    assert hass.states.get(eid).state != first


async def test_fetch_failure_keeps_last_image(hass, hass_client, config_entry, fake_client, freezer):
    await _setup(hass, config_entry, fake_client)
    fake_client.image_error = TellyboxConnectionError("down")
    freezer.tick(timedelta(hours=2))
    await push_state(hass, fake_client)
    assert fake_client.image_paths.count("/static/avatars/fox.svg") == 2
    assert hass.states.get(_eid(hass)).state != STATE_UNAVAILABLE
    resp = await _body(hass, hass_client)
    assert resp.status == 200
    assert await resp.read() == TINY_SVG


async def test_first_fetch_failure_is_not_fatal(hass, hass_client, config_entry, fake_client):
    fake_client.image_error = TellyboxConnectionError("down")
    await _setup(hass, config_entry, fake_client)
    assert hass.states.get(_eid(hass)) is not None
    fake_client.image_error = None
    resp = await _body(hass, hass_client)  # first use fetches
    assert resp.status == 200
    assert await resp.read() == TINY_SVG
