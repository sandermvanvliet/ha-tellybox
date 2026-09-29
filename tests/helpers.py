"""Fixtures for the core tests (setup, coordinator, flow, actions): no platforms, so they don't depend on entities."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.helpers import device_registry as dr

from custom_components.tellybox.const import DOMAIN, main_device_identifier, profile_device_identifier

from .conftest import INSTANCE_ID


@pytest.fixture
def no_platforms():
    with patch("custom_components.tellybox.PLATFORMS", []):
        yield


@pytest.fixture
async def core(hass, config_entry, patch_client, no_platforms):
    """Set up the integration without platforms; returns the fake client."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return patch_client


def add_devices(hass, config_entry, *profile_ids: int) -> dict[str, str]:
    """Register the Tellybox device and kid devices; returns {"main": id, 1: id, ...} (keys as str/int)."""
    registry = dr.async_get(hass)
    ids: dict = {}
    main = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={main_device_identifier(INSTANCE_ID)}, name="Tellybox"
    )
    ids["main"] = main.id
    for pid in profile_ids:
        dev = registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={profile_device_identifier(INSTANCE_ID, pid)}, name=f"Kid {pid}",
        )
        ids[pid] = dev.id
    return ids
