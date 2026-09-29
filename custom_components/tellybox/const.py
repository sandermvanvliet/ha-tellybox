"""Constants for the Tellybox integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "tellybox"
MANUFACTURER: Final = "Tellybox"

CONF_URL: Final = "url"  # the Tellybox base URL, e.g. https://tellybox.example
CONF_TOKEN: Final = "token"  # an API token (tbx_...) from Tellybox's Integrations page
CONF_CONTROL: Final = "control"  # option: create override buttons and allow override actions (default True)

# The event stream reconnects with exponential backoff; entities go unavailable only after this long down,
# so a Wi-Fi blip doesn't make them flap.
RECONNECT_MIN_S: Final = 1.0
RECONNECT_MAX_S: Final = 60.0
UNAVAILABLE_AFTER_S: Final = 60.0

EXTRA_MINUTES_MAX: Final = 240

# Services (actions). Each takes a `device_id` list: the Tellybox device = everyone, a kid's device = that kid.
SERVICE_ADD_TIME: Final = "add_time"  # + minutes (1..240)
SERVICE_SET_UNLIMITED_TODAY: Final = "set_unlimited_today"
SERVICE_BLOCK_TODAY: Final = "block_today"
SERVICE_CLEAR_OVERRIDES: Final = "clear_overrides"
SERVICE_STOP_NOW: Final = "stop_now"
SERVICE_PLAY_EPISODE: Final = "play_episode"  # episode_id; kids from kid devices, else the last watchers
ATTR_MINUTES: Final = "minutes"
ATTR_EPISODE_ID: Final = "episode_id"


def main_device_identifier(instance_id: str) -> tuple[str, str]:
    """The Tellybox device (one per server, keyed on its instance id)."""
    return (DOMAIN, instance_id)


def profile_device_identifier(instance_id: str, profile_id: int) -> tuple[str, str]:
    """A kid's device, `via_device` the Tellybox device."""
    return (DOMAIN, f"{instance_id}_profile_{profile_id}")
