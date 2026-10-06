"""Diagnostics never contain the token or URL."""

from __future__ import annotations

import json

from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from .conftest import INSTANCE_ID, TOKEN, URL
from .helpers import core, no_platforms  # noqa: F401


async def test_diagnostics(hass, hass_client, core, config_entry):
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["entry"] == {"url": REDACTED, "token": REDACTED}
    assert diag["options"] == {"control": True}
    assert diag["state"]["profiles"][0]["name"] == "Mila"
    dumped = json.dumps(diag)
    assert TOKEN not in dumped and URL not in dumped and INSTANCE_ID not in dumped


async def test_diagnostics_redact_in_app_session(hass, hass_client, patch_client, no_platforms, config_entry):
    """Browser device ids and labels of in-app sessions are redacted, also inside the sessions list."""
    patch_client.state_data["sessions"].append(
        {"key": "device:dev-secret-1", "target": "device", "label": "Living room tablet", "device_id": "dev-secret-1",
         "episode_id": 4, "show_id": 2, "title": "Alongside", "state": "playing", "position_s": 10,
         "duration_s": 660, "profile_ids": [2]}
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    sessions = diag["state"]["sessions"]
    assert len(sessions) == 2
    tv, in_app = sessions
    assert tv["label"] == REDACTED
    assert tv["device_id"] is None  # async_redact_data leaves None values as they are
    assert in_app["label"] == REDACTED
    assert in_app["device_id"] == REDACTED
    assert in_app["key"] == REDACTED  # "device:<device_id>" carries the browser id too
    dumped = json.dumps(diag)
    assert "Living room tablet" not in dumped and "dev-secret-1" not in dumped
