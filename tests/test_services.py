"""The actions and their device targeting."""

from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytellybox import TellyboxTimeUpError

from custom_components.tellybox.const import CONF_CONTROL, DOMAIN

from .helpers import add_devices, core, no_platforms  # noqa: F401


async def call(hass, service, **data):
    await hass.services.async_call(DOMAIN, service, data, blocking=True)


@pytest.fixture
async def ids(hass, core, config_entry):
    return add_devices(hass, config_entry, 1, 2)


async def test_add_time_everyone(hass, core, ids):
    await call(hass, "add_time", device_id=ids["main"], minutes=15)
    assert ("add_time", 15) in core.calls and ("add_time_targets", None) in core.calls


async def test_add_time_kids(hass, core, ids):
    await call(hass, "add_time", device_id=[ids[1], ids[2]], minutes=30)
    assert ("add_time_targets", [1, 2]) in core.calls


async def test_add_time_single_kid_string(hass, core, ids):
    await call(hass, "add_time", device_id=ids[2], minutes=5)
    assert ("add_time_targets", [2]) in core.calls


@pytest.mark.parametrize("minutes", [0, 241])
async def test_add_time_range(hass, core, ids, minutes):
    with pytest.raises(Exception):  # vol.Invalid
        await call(hass, "add_time", device_id=ids["main"], minutes=minutes)


@pytest.mark.parametrize(("service", "name"), [("set_unlimited_today", "set_unlimited"), ("block_today", "block"),
                                                ("clear_overrides", "clear_today")])
async def test_overrides(hass, core, ids, service, name):
    await call(hass, service, device_id=ids[1])
    assert (name, [1]) in core.calls
    await call(hass, service, device_id=ids["main"])
    assert (name, None) in core.calls


async def test_stop_now(hass, core, ids):
    await call(hass, "stop_now", device_id=ids["main"])
    assert ("stop_now",) in core.calls


async def test_mixed_targets_refused(hass, core, ids):
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "block_today", device_id=[ids["main"], ids[1]])
    assert err.value.translation_key == "mixed_targets"
    assert not [c for c in core.calls if c[0] == "block"]


async def test_foreign_device_refused(hass, core, ids):
    other = dr.async_get(hass)
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    e = MockConfigEntry(domain="other")
    e.add_to_hass(hass)
    dev = other.async_get_or_create(config_entry_id=e.entry_id, identifiers={("other", "x")})
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "block_today", device_id=dev.id)
    assert err.value.translation_key == "invalid_target"
    with pytest.raises(ServiceValidationError):
        await call(hass, "block_today", device_id="nope")


async def test_control_disabled(hass, core, config_entry, ids):
    hass.config_entries.async_update_entry(config_entry, options={CONF_CONTROL: False})
    await hass.async_block_till_done()
    ids = add_devices(hass, config_entry, 1)
    for service, extra in [("add_time", {"minutes": 5}), ("block_today", {}), ("stop_now", {})]:
        with pytest.raises(ServiceValidationError) as err:
            await call(hass, service, device_id=ids["main"], **extra)
        assert err.value.translation_key == "control_disabled"
    # playing is a kid action, not an override: still allowed
    await call(hass, "play_episode", device_id=ids[1], episode_id=4)
    assert ("play", 4, [1]) in core.calls


async def test_play_kids(hass, core, ids):
    await call(hass, "play_episode", device_id=ids[1], episode_id=4)
    assert ("play", 4, [1]) in core.calls


async def test_play_uses_last_watchers_for_main(hass, core, ids):
    await call(hass, "play_episode", device_id=ids["main"], episode_id=4)
    assert ("play", 4, [1]) in core.calls


async def test_play_no_kids(hass, core, config_entry, ids):
    config_entry.runtime_data.coordinator._last_watchers = ()
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "play_episode", device_id=ids["main"], episode_id=4)
    assert err.value.translation_key == "no_kids"


async def test_play_time_up_is_translated(hass, core, ids):
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "play_episode", device_id=ids[2], episode_id=4)  # Noah can't start
    assert err.value.translation_key == "time_up"


async def test_forbidden_read_only_token(hass, core, ids):
    core.read_only = True
    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "block_today", device_id=ids["main"])
    assert err.value.translation_key == "forbidden"
