"""Diagnostics: the entry (token and URL redacted), its options and the last state."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, CONF_URL
from .coordinator import TellyboxConfigEntry

TO_REDACT = {CONF_TOKEN, CONF_URL, "url", "token", "instance_id", "device"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: TellyboxConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data.coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "state": async_redact_data(data.raw, TO_REDACT) if data is not None else None,
    }
