"""The Tellybox integration: live state and parent controls for a Tellybox server.

Contract only: subagent B implements setup and unload (see docs/plan.md).
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pytellybox import TellyboxClient  # noqa: F401  (tests patch it here)

from .coordinator import TellyboxConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.MEDIA_PLAYER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TellyboxConfigEntry) -> bool:
    """Create the client (HA's shared aiohttp session), the coordinator (first refresh, then start the event
    stream), set `entry.runtime_data`, forward PLATFORMS, reload on options change, and remove the devices of
    kids that no longer exist whenever the state changes."""
    raise NotImplementedError


async def async_unload_entry(hass: HomeAssistant, entry: TellyboxConfigEntry) -> bool:
    raise NotImplementedError
