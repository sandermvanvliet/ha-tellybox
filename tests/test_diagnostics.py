"""Diagnostics never contain the token or URL."""

from __future__ import annotations

import json

from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from .conftest import INSTANCE_ID, TOKEN, URL
from .helpers import core, no_platforms, tolerate_null_entity_names  # noqa: F401


async def test_diagnostics(hass, hass_client, core, config_entry):
    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag["entry"] == {"url": REDACTED, "token": REDACTED}
    assert diag["options"] == {"control": True}
    assert diag["state"]["profiles"][0]["name"] == "Mila"
    dumped = json.dumps(diag)
    assert TOKEN not in dumped and URL not in dumped and INSTANCE_ID not in dumped
