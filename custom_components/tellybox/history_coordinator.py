"""Viewing history (HA-12): polled every HISTORY_POLL_S and again at the daily rollover."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pytellybox import TellyboxAuthError, TellyboxClient, TellyboxError, UsageHistory

from .const import DOMAIN, HISTORY_POLL_S
from .coordinator import TellyboxConfigEntry, TellyboxCoordinator

_LOGGER = logging.getLogger(__name__)

HISTORY_DAYS = 8  # today plus the 7 completed days before it


class TellyboxHistoryCoordinator(DataUpdateCoordinator[UsageHistory]):
    """Daily totals and the last watched episode per kid.

    - Polls `client.history(days=8)` every HISTORY_POLL_S. A 401 starts reauth (ConfigEntryAuthFailed, which
      DataUpdateCoordinator turns into `entry.async_start_reauth`); any other error is an UpdateFailed, so the
      last data stays and entities go unavailable until the next success.
    - `async_watch_rollover(main)` refreshes when the main state's `day.date` changes.
    """

    config_entry: TellyboxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TellyboxConfigEntry, client: TellyboxClient) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} history",
            update_interval=timedelta(seconds=HISTORY_POLL_S),
        )
        self._client = client

    async def _async_update_data(self) -> UsageHistory:
        try:
            return await self._client.history(days=HISTORY_DAYS)
        except TellyboxAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (TellyboxError, OSError, TimeoutError) as err:
            raise UpdateFailed(f"Can't get Tellybox's history: {err}") from err

    def async_watch_rollover(self, main: TellyboxCoordinator) -> Callable[[], None]:
        """Request a refresh whenever `main.data.day.date` changes; returns the listener's remover."""
        last: date | None = main.data.day.date if main.data else None

        @callback
        def _on_state() -> None:
            nonlocal last
            current = main.data.day.date if main.data else None
            if current is None or current == last:
                return
            last = current
            self.config_entry.async_create_task(self.hass, self.async_request_refresh())

        remove: CALLBACK_TYPE = main.async_add_listener(_on_state)
        return remove
