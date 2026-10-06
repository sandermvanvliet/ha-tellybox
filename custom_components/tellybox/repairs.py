"""Repairs issues derived from the live admin state: TV unreachable, kid without shows, failing subscriptions,
low disk. Pure in-memory logic (no I/O): it reads `coordinator.data`, the entry options and the clock."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DISK_FREE_GB,
    CONF_TV_UNREACHABLE_MINUTES,
    DEFAULT_DISK_FREE_GB,
    DEFAULT_TV_UNREACHABLE_MINUTES,
    DISK_HYSTERESIS,
    DOMAIN,
    ISSUE_DISK_LOW,
    ISSUE_NO_VISIBLE_SHOWS,
    ISSUE_SUBSCRIPTIONS_UNHEALTHY,
    ISSUE_TV_UNREACHABLE,
    NO_VISIBLE_SHOWS_GRACE_S,
)
from .coordinator import TellyboxConfigEntry, TellyboxCoordinator

GB = 1e9  # the disk threshold and the {free_gb} placeholder use decimal gigabytes (1 GB = 10^9 bytes)


class TellyboxRepairs:
    """Creates an issue on the false-to-true transition of a condition and deletes it on true-to-false."""

    def __init__(self, hass: HomeAssistant, entry: TellyboxConfigEntry, coordinator: TellyboxCoordinator) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._since: dict[str, datetime] = {}
        self._active: set[str] = set()

    def _id(self, key: str) -> str:
        return f"{self._entry.entry_id}_{key}"

    def _create(self, issue_id: str, translation_key: str, placeholders: dict[str, str]) -> None:
        if issue_id in self._active:
            return
        self._active.add(issue_id)
        ir.async_create_issue(
            self._hass, DOMAIN, issue_id, is_fixable=False, is_persistent=False,
            severity=ir.IssueSeverity.WARNING, translation_key=translation_key,
            translation_placeholders=placeholders,
        )

    def _delete(self, issue_id: str) -> None:
        if issue_id in self._active:
            self._active.discard(issue_id)
            ir.async_delete_issue(self._hass, DOMAIN, issue_id)

    @callback
    def async_evaluate(self) -> None:
        coordinator = self._coordinator
        state = coordinator.data
        if state is None or not coordinator.last_update_success:
            return  # stale or missing: neither create nor clear
        now = dt_util.utcnow()
        options = self._entry.options

        # TV
        issue_id = self._id(ISSUE_TV_UNREACHABLE)
        minutes = options.get(CONF_TV_UNREACHABLE_MINUTES, DEFAULT_TV_UNREACHABLE_MINUTES)
        if minutes <= 0 or state.tv.reachable:
            self._since.pop(issue_id, None)
            self._delete(issue_id)
        else:
            since = self._since.setdefault(issue_id, now)
            if (now - since).total_seconds() >= minutes * 60:
                self._create(issue_id, ISSUE_TV_UNREACHABLE, {"minutes": str(minutes)})

        # Kids without visible shows
        prefix = self._id(f"{ISSUE_NO_VISIBLE_SHOWS}_")
        seen: set[str] = set()
        for profile in state.profiles:
            issue_id = f"{prefix}{profile.id}"
            seen.add(issue_id)
            if profile.visible_shows is None:
                continue  # unknown (old server): no issue, change nothing
            if profile.visible_shows != 0:
                self._since.pop(issue_id, None)
                self._delete(issue_id)
                continue
            since = self._since.setdefault(issue_id, now)
            if (now - since).total_seconds() >= NO_VISIBLE_SHOWS_GRACE_S:
                self._create(issue_id, ISSUE_NO_VISIBLE_SHOWS, {"name": profile.name})
        for issue_id in [i for i in self._active | set(self._since) if i.startswith(prefix) and i not in seen]:
            self._since.pop(issue_id, None)
            self._delete(issue_id)

        # Subscriptions
        issue_id = self._id(ISSUE_SUBSCRIPTIONS_UNHEALTHY)
        if state.inbox.unhealthy > 0:
            self._create(issue_id, ISSUE_SUBSCRIPTIONS_UNHEALTHY, {"count": str(state.inbox.unhealthy)})
        else:
            self._delete(issue_id)

        # Disk, with hysteresis
        issue_id = self._id(ISSUE_DISK_LOW)
        threshold_gb = options.get(CONF_DISK_FREE_GB, DEFAULT_DISK_FREE_GB)
        free = state.disk.free_bytes
        if threshold_gb <= 0:
            self._delete(issue_id)
        elif free is not None:
            threshold = threshold_gb * GB
            if issue_id in self._active:
                if free >= threshold * DISK_HYSTERESIS:
                    self._delete(issue_id)
            elif free < threshold:
                self._create(issue_id, ISSUE_DISK_LOW,
                             {"free_gb": f"{free / GB:.1f}", "threshold_gb": str(int(threshold_gb))})

    @callback
    def async_clear(self) -> None:
        for issue_id in list(self._active):
            self._delete(issue_id)
        self._since.clear()
