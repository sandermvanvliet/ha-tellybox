"""Helpers for testing the blueprints in `blueprints/automation/tellybox/`.

Verified facts (T1, 2026-10-06):

* HACS (category `integration`) installs only `custom_components/<domain>` from the repository. Files
  elsewhere, including the root `blueprints/` directory, are not installed, so users import blueprints by
  URL (`source_url` on `main`, "My Home Assistant" import badges). Home Assistant core can bundle blueprints
  with an integration, custom integrations cannot.
* hassfest validates `custom_components/<domain>` (manifest, translations, services, ...) and does not
  look at other top-level directories; the HACS action (category integration) checks `hacs.json`, the
  manifest and that exactly one `custom_components/<domain>` exists, and does not reject other root
  directories (`docs/`, `tests/`, `scripts/` already exist here). No offline copy of either action's
  documentation is available in this environment, so CI on the first pull request must confirm that a root
  `blueprints/` directory is accepted.

Writing a blueprint test (the pattern):

    async def test_x(hass, config_entry, fake_client):
        calls = async_mock_service(hass, "test", "record")
        await automation_from_blueprint(hass, "five_minute_warning.yaml", {
            "last_five_sensor": "binary_sensor.some",
            "warning_actions": [{"action": "test.record", "data": {"kid": "{{ kid }}"}}],
        })
        hass.states.async_set("binary_sensor.some", "on")
        await hass.async_block_till_done()
        assert len(calls) == 1

Use `setup_platform` + `fake_client.set_profile/set_state` for real integration entities.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

BLUEPRINT_DIR = Path(__file__).parent.parent / "blueprints" / "automation" / "tellybox"
TARGET = "blueprints/automation/tellybox/"


def install_blueprint(hass: HomeAssistant, filename: str) -> str:
    """Copy a blueprint into the test config dir; return the `use_blueprint.path` for it."""
    target = Path(hass.config.path(TARGET))
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(BLUEPRINT_DIR / filename, target / filename)
    return f"tellybox/{filename}"


async def automation_from_blueprint(
    hass: HomeAssistant, filename: str, inputs: dict[str, Any], *, instance: int = 0
) -> None:
    """Set up the automation component with one automation using the blueprint.

    `instance` is used for the automation id, so a second call can add another automation
    (note that each call sets the component up again; pass all automations in one test sparingly).
    """
    path = install_blueprint(hass, filename)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": f"blueprint_test_{instance}",
                    "alias": f"Blueprint test {instance}",
                    "use_blueprint": {"path": path, "input": inputs},
                }
            ]
        },
    )
    await hass.async_block_till_done()
