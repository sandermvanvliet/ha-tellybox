"""Repairs issues: TV unreachable, kid without shows, failing subscriptions, low disk."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytellybox import TellyboxConnectionError

from custom_components.tellybox.const import (
    CONF_CONTROL,
    CONF_DISK_FREE_GB,
    CONF_TV_UNREACHABLE_MINUTES,
    DOMAIN,
    NO_VISIBLE_SHOWS_GRACE_S,
    UNAVAILABLE_AFTER_S,
)

from .helpers import no_platforms  # noqa: F401

GB = 10**9


async def tick(hass, freezer, seconds: float) -> None:
    """Advance time in steps of at most 60 s, so the one-minute interval fires the way it would live."""
    while seconds > 0:
        step = min(seconds, 60)
        seconds -= step
        freezer.tick(timedelta(seconds=step))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()


async def start(hass, config_entry, patch_client, no_platforms, **options):  # noqa: F811
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_CONTROL: True, **options})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return patch_client


def issue(hass, config_entry, key):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{config_entry.entry_id}_{key}")


def tellybox_issues(hass):
    return [i for (d, _), i in ir.async_get(hass).issues.items() if d == DOMAIN]


@pytest.fixture
async def fake(hass, config_entry, patch_client, no_platforms):  # noqa: F811
    return await start(hass, config_entry, patch_client, no_platforms)


async def test_fixture_state_creates_nothing(hass, fake):
    assert tellybox_issues(hass) == []


# -- TV

async def test_tv_issue_after_grace_and_clears(hass, config_entry, fake, freezer):
    fake.set_state(tv={"connection": "UNREACHABLE", "reachable": False, "device": "TV"})
    await hass.async_block_till_done()
    await tick(hass, freezer, 59 * 60)
    assert issue(hass, config_entry, "tv_unreachable") is None
    await tick(hass, freezer, 61)
    found = issue(hass, config_entry, "tv_unreachable")
    assert found.translation_key == "tv_unreachable"
    assert found.translation_placeholders == {"minutes": "60"}
    assert not found.is_fixable and not found.is_persistent
    assert found.severity == ir.IssueSeverity.WARNING and found.learn_more_url is None
    fake.set_state(tv={"connection": "CONNECTED", "reachable": True, "device": "TV"})
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "tv_unreachable") is None


async def test_tv_disabled_with_zero(hass, config_entry, patch_client, no_platforms, freezer):
    fake = await start(hass, config_entry, patch_client, no_platforms, **{CONF_TV_UNREACHABLE_MINUTES: 0})
    fake.set_state(tv={"connection": "UNREACHABLE", "reachable": False, "device": "TV"})
    await hass.async_block_till_done()
    await tick(hass, freezer, 24 * 3600)
    assert issue(hass, config_entry, "tv_unreachable") is None


async def test_tv_blip_restarts_timer(hass, config_entry, patch_client, no_platforms, freezer):
    fake = await start(hass, config_entry, patch_client, no_platforms, **{CONF_TV_UNREACHABLE_MINUTES: 10})
    down = {"connection": "UNREACHABLE", "reachable": False, "device": "TV"}
    up = {"connection": "CONNECTED", "reachable": True, "device": "TV"}
    fake.set_state(tv=down)
    await hass.async_block_till_done()
    await tick(hass, freezer, 9 * 60)
    fake.set_state(tv=up)
    await hass.async_block_till_done()
    fake.set_state(tv=down)
    await hass.async_block_till_done()
    await tick(hass, freezer, 9 * 60)
    assert issue(hass, config_entry, "tv_unreachable") is None
    await tick(hass, freezer, 61)
    found = issue(hass, config_entry, "tv_unreachable")
    assert found.translation_placeholders == {"minutes": "10"}


async def test_tv_interval_fires_without_events(hass, config_entry, patch_client, no_platforms, freezer):
    fake = await start(hass, config_entry, patch_client, no_platforms, **{CONF_TV_UNREACHABLE_MINUTES: 5})
    fake.set_state(tv={"connection": "UNREACHABLE", "reachable": False, "device": "TV"})
    await hass.async_block_till_done()
    for _ in range(6):  # no events, only the 60 s interval
        await tick(hass, freezer, 60)
    assert issue(hass, config_entry, "tv_unreachable") is not None


# -- no visible shows

async def test_no_visible_shows(hass, config_entry, fake, freezer):
    fake.set_profile(1, visible_shows=0)
    await hass.async_block_till_done()
    await tick(hass, freezer, 600)
    assert issue(hass, config_entry, "no_visible_shows_1") is None  # 10 minutes is within the grace
    await tick(hass, freezer, NO_VISIBLE_SHOWS_GRACE_S)
    found = issue(hass, config_entry, "no_visible_shows_1")
    assert found.translation_key == "no_visible_shows"
    assert found.translation_placeholders == {"name": "Mila"}
    assert issue(hass, config_entry, "no_visible_shows_2") is None
    assert len(tellybox_issues(hass)) == 1
    fake.set_profile(1, visible_shows=2)
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "no_visible_shows_1") is None


async def test_unknown_visible_shows_creates_nothing(hass, config_entry, fake, freezer):
    fake.set_profile(1, visible_shows=None)
    await hass.async_block_till_done()
    await tick(hass, freezer, NO_VISIBLE_SHOWS_GRACE_S + 60)
    assert tellybox_issues(hass) == []


async def test_removed_kid_deletes_issue(hass, config_entry, fake, freezer):
    fake.set_profile(2, visible_shows=0)
    await hass.async_block_till_done()
    await tick(hass, freezer, NO_VISIBLE_SHOWS_GRACE_S + 60)
    assert issue(hass, config_entry, "no_visible_shows_2") is not None
    fake.state_data["profiles"] = [p for p in fake.state_data["profiles"] if p["id"] != 2]
    fake.push()
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "no_visible_shows_2") is None


# -- subscriptions

async def test_subscriptions_unhealthy(hass, config_entry, fake):
    inbox = {**fake.state_data["inbox"], "unhealthy": 2}
    fake.set_state(inbox=inbox)
    await hass.async_block_till_done()
    found = issue(hass, config_entry, "subscriptions_unhealthy")
    assert found.translation_key == "subscriptions_unhealthy"
    assert found.translation_placeholders == {"count": "2"}
    fake.set_state(inbox={**inbox, "unhealthy": 0})
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "subscriptions_unhealthy") is None


# -- disk

def disk(fake, free):
    fake.set_state(disk={**fake.state_data["disk"], "free_bytes": free})


async def test_disk_low_with_hysteresis(hass, config_entry, fake):
    disk(fake, 4_500_000_000)
    await hass.async_block_till_done()
    found = issue(hass, config_entry, "disk_low")
    assert found.translation_key == "disk_low"
    assert found.translation_placeholders == {"free_gb": "4.5", "threshold_gb": "5"}
    disk(fake, 5_200_000_000)  # above the threshold, below 1.1x: stays
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "disk_low") is not None
    disk(fake, 5_500_000_000)  # 1.1x clears
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "disk_low") is None
    disk(fake, 5_200_000_000)  # not below the threshold: no new issue
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "disk_low") is None


async def test_disk_unknown_creates_nothing(hass, config_entry, fake):
    disk(fake, None)
    await hass.async_block_till_done()
    assert tellybox_issues(hass) == []


async def test_disk_disabled_with_zero(hass, config_entry, patch_client, no_platforms):
    fake = await start(hass, config_entry, patch_client, no_platforms, **{CONF_DISK_FREE_GB: 0})
    disk(fake, 1 * GB)
    await hass.async_block_till_done()
    assert tellybox_issues(hass) == []


# -- stale data, spam, unload, ids

async def test_stale_data_neither_creates_nor_clears(hass, config_entry, fake, freezer):
    coordinator = config_entry.runtime_data.coordinator
    inbox = {**fake.state_data["inbox"], "unhealthy": 1}
    fake.set_state(inbox=inbox)
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "subscriptions_unhealthy") is not None
    fake.fail_with = TellyboxConnectionError("down")
    fake.break_stream()
    await hass.async_block_till_done()
    await tick(hass, freezer, UNAVAILABLE_AFTER_S + 1)
    assert not coordinator.last_update_success
    # pretend the data changed while stale: disk low would be new, unhealthy 0 would clear
    object.__setattr__(coordinator.data.disk, "free_bytes", 1 * GB)
    object.__setattr__(coordinator.data.inbox, "unhealthy", 0)
    coordinator.async_update_listeners()
    await tick(hass, freezer, 60)
    assert issue(hass, config_entry, "subscriptions_unhealthy") is not None
    assert issue(hass, config_entry, "disk_low") is None
    fake.fail_with = None
    fake.state_data["inbox"]["unhealthy"] = 0
    fake.state_data["disk"]["free_bytes"] = 1 * GB
    await tick(hass, freezer, 70)
    assert coordinator.last_update_success
    assert issue(hass, config_entry, "subscriptions_unhealthy") is None
    assert issue(hass, config_entry, "disk_low") is not None


async def test_no_spam_one_create_call(hass, config_entry, fake):
    fake.set_state(inbox={**fake.state_data["inbox"], "unhealthy": 3})
    await hass.async_block_till_done()
    with patch("custom_components.tellybox.repairs.ir.async_create_issue") as spy:
        for n in range(10):
            fake.set_profile(1, remaining_s=100 + n)
            await hass.async_block_till_done()
        assert spy.call_count == 0
    # and from the start: exactly one call across ten updates
    fake.set_state(inbox={**fake.state_data["inbox"], "unhealthy": 0})
    await hass.async_block_till_done()
    assert issue(hass, config_entry, "subscriptions_unhealthy") is None
    with patch("custom_components.tellybox.repairs.ir.async_create_issue") as spy:
        fake.set_state(inbox={**fake.state_data["inbox"], "unhealthy": 3})
        await hass.async_block_till_done()
        for n in range(10):
            fake.set_profile(1, remaining_s=200 + n)
            await hass.async_block_till_done()
        assert spy.call_count == 1


async def test_unload_removes_all_issues(hass, config_entry, fake):
    fake.set_state(inbox={**fake.state_data["inbox"], "unhealthy": 1})
    disk(fake, 1 * GB)
    await hass.async_block_till_done()
    assert len(tellybox_issues(hass)) == 2
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert tellybox_issues(hass) == []


async def test_issue_ids_contain_entry_id(hass, config_entry, fake):
    fake.set_state(inbox={**fake.state_data["inbox"], "unhealthy": 1})
    disk(fake, 1 * GB)
    await hass.async_block_till_done()
    ids = sorted(i.issue_id for i in tellybox_issues(hass))
    assert ids == sorted(f"{config_entry.entry_id}_{k}" for k in ("disk_low", "subscriptions_unhealthy"))
