"""Per-session sensors for in-app playback: creation, updates, delayed removal, sweep, disabled entities."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.tellybox.const import DOMAIN

from .conftest import INSTANCE_ID
from .platform_helpers import push_state, setup_platform

TV = {"key": "tv", "target": "tv", "label": "TV", "device_id": None, "episode_id": 4, "show_id": 2,
      "title": "Alongside", "state": "playing", "position_s": 5, "duration_s": 300, "profile_ids": [1]}


def phone(device_id="abc12345", label="iPhone Safari", state="playing", position_s=10, episode_id=5, profile_ids=(2,)):
    return {"key": f"device:{device_id}", "target": "device", "label": label, "device_id": device_id,
            "episode_id": episode_id, "show_id": 2, "title": "Lost Ball", "state": state,
            "position_s": position_s, "duration_s": 600, "profile_ids": list(profile_ids)}


def uid(device_id="abc12345"):
    return f"{INSTANCE_ID}_session_{device_id}"


def reg_id(hass, device_id="abc12345"):
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, uid(device_id))


def session_entries(hass):
    return [e for e in er.async_get(hass).entities.values()
            if e.platform == DOMAIN and e.unique_id.startswith(f"{INSTANCE_ID}_session_")]


async def tick(hass, freezer, seconds):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def _setup(hass, config_entry, fake_client, sessions=None):
    if sessions is not None:
        fake_client.state_data["sessions"] = sessions
    return await setup_platform(hass, config_entry, fake_client, Platform.SENSOR)


async def test_creation_state_and_attributes(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [TV, phone()])
    entity_id = reg_id(hass)
    assert entity_id == "sensor.tellybox_watching_on_iphone_safari"
    state = hass.states.get(entity_id)
    assert state.state == "playing"
    attrs = state.attributes
    assert attrs["label"] == "iPhone Safari"
    assert attrs["title"] == "Lost Ball"
    assert attrs["show_id"] == 2
    assert attrs["episode_id"] == 5
    assert attrs["kids"] == ["Noah"]
    assert attrs["profile_ids"] == [2]
    assert attrs["position_s"] == 10
    assert attrs["duration_s"] == 600
    assert "device_id" not in attrs
    assert "abc12345" not in str(dict(attrs))
    assert state.attributes["options"] == ["loading", "playing", "paused", "buffering"]


async def test_update_state_and_position(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [phone()])
    fake_client.set_state(sessions=[phone(state="paused", position_s=40)])
    await push_state(hass, fake_client)
    state = hass.states.get(reg_id(hass))
    assert state.state == "paused"
    assert state.attributes["position_s"] == 40


async def test_appears_after_setup(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client)
    assert session_entries(hass) == []
    fake_client.set_state(sessions=[phone()])
    await push_state(hass, fake_client)
    assert hass.states.get(reg_id(hass)).state == "playing"


async def test_same_key_across_episode_change_keeps_one_entity(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [phone(episode_id=5)])
    first = reg_id(hass)
    fake_client.set_state(sessions=[phone(episode_id=6, state="loading", position_s=0)])
    await push_state(hass, fake_client)
    assert len(session_entries(hass)) == 1
    assert reg_id(hass) == first
    state = hass.states.get(first)
    assert state.state == "loading"
    assert state.attributes["episode_id"] == 6


async def test_removed_after_30_seconds_absence(hass, config_entry, fake_client, freezer):
    await _setup(hass, config_entry, fake_client, [phone()])
    entity_id = reg_id(hass)
    fake_client.set_state(sessions=[])
    await push_state(hass, fake_client)
    assert hass.states.get(entity_id).state == "unavailable"
    await tick(hass, freezer, 29)
    assert reg_id(hass) == entity_id
    await tick(hass, freezer, 2)
    assert reg_id(hass) is None
    assert hass.states.get(entity_id) is None
    assert session_entries(hass) == []


async def test_return_within_30_seconds_keeps_entity(hass, config_entry, fake_client, freezer):
    await _setup(hass, config_entry, fake_client, [phone()])
    entity_id = reg_id(hass)
    fake_client.set_state(sessions=[])
    await push_state(hass, fake_client)
    await tick(hass, freezer, 20)
    fake_client.set_state(sessions=[phone(state="paused")])
    await push_state(hass, fake_client)
    await tick(hass, freezer, 60)
    assert reg_id(hass) == entity_id
    assert hass.states.get(entity_id).state == "paused"
    assert len(session_entries(hass)) == 1


async def test_return_after_removal_creates_it_again(hass, config_entry, fake_client, freezer):
    await _setup(hass, config_entry, fake_client, [phone()])
    fake_client.set_state(sessions=[])
    await push_state(hass, fake_client)
    await tick(hass, freezer, 31)
    assert session_entries(hass) == []
    fake_client.set_state(sessions=[phone()])
    await push_state(hass, fake_client)
    assert hass.states.get(reg_id(hass)).state == "playing"


async def test_two_browsers_with_the_same_label_are_distinct(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client,
                 [phone("abc12345", profile_ids=(1,)), phone("def67890", profile_ids=(2,))])
    first, second = reg_id(hass, "abc12345"), reg_id(hass, "def67890")
    assert first and second and first != second
    assert {first, second} == {"sensor.tellybox_watching_on_iphone_safari",
                               "sensor.tellybox_watching_on_iphone_safari_2"}
    assert hass.states.get(first).attributes["kids"] == ["Mila"]
    assert hass.states.get(second).attributes["kids"] == ["Noah"]


async def test_leftover_registry_entry_is_swept_at_setup(hass, config_entry, fake_client):
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, uid("gone0001"), config_entry=config_entry,
                                 suggested_object_id="tellybox_watching_on_old_phone")
    registry.async_get_or_create("sensor", DOMAIN, uid("abc12345"), config_entry=config_entry,
                                 suggested_object_id="tellybox_watching_on_iphone_safari")
    fake_client.state_data["sessions"] = [phone()]
    await setup_platform(hass, config_entry, fake_client, Platform.SENSOR)
    assert reg_id(hass, "gone0001") is None
    assert reg_id(hass, "abc12345") is not None
    assert hass.states.get(reg_id(hass, "abc12345")).state == "playing"


async def test_disabled_entity_is_not_recreated(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [phone()])
    entity_id = reg_id(hass)
    registry = er.async_get(hass)
    registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()  # the config entry reloads
    assert hass.states.get(entity_id) is None
    fake_client.set_state(sessions=[phone(state="paused")])
    await push_state(hass, fake_client)
    assert hass.states.get(entity_id) is None
    assert registry.async_get(entity_id).disabled
    assert len(session_entries(hass)) == 1


async def test_no_sessions_gives_no_entities(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [])
    assert session_entries(hass) == []


async def test_state_without_sessions_key_gives_no_entities(hass, config_entry, fake_client):
    fake_client.state_data.pop("sessions", None)
    await _setup(hass, config_entry, fake_client)
    assert session_entries(hass) == []
    fake_client.push()
    await hass.async_block_till_done()
    assert session_entries(hass) == []


async def test_tv_session_never_creates_one(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [TV])
    assert session_entries(hass) == []
    fake_client.set_state(sessions=[TV, phone()])
    await push_state(hass, fake_client)
    assert len(session_entries(hass)) == 1


async def test_unload_cancels_pending_timers(hass, config_entry, fake_client):
    await _setup(hass, config_entry, fake_client, [phone()])
    fake_client.set_state(sessions=[])
    await push_state(hass, fake_client)  # a removal is now scheduled
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    # the harness fails the test on a lingering timer; the registry entry is untouched by an unload
    assert reg_id(hass) is not None
