"""Sensors: the Tellybox device (now playing, time left, downloads, disk) and each kid's time."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pytellybox import AdminState, Profile, ProfileUsage

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .history_coordinator import TellyboxHistoryCoordinator
from .entity import TellyboxEntity, TellyboxProfileEntity, add_profile_entities
from .session_sensor import async_setup_session_sensors
from .sessions import session_for_profile

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TellyboxSensorDescription(SensorEntityDescription):
    """A sensor on the Tellybox device."""

    value_fn: Callable[[AdminState], int | float | str | datetime | None]
    attrs_fn: Callable[[AdminState], Mapping[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class TellyboxProfileSensorDescription(SensorEntityDescription):
    """A sensor on a kid's device."""

    value_fn: Callable[[Profile], int | float | str | None] = lambda _p: None
    state_value_fn: Callable[[AdminState, Profile], int | float | str | None] | None = None  # needs the sessions
    attrs_fn: Callable[[AdminState, Profile], Mapping[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class TellyboxHistorySensorDescription(SensorEntityDescription):
    """A history sensor on a kid's device (HA-12); the value comes from that kid's `ProfileUsage`, or None."""

    value_fn: Callable[[ProfileUsage | None], int | float | datetime | None]
    attrs_fn: Callable[[ProfileUsage | None], Mapping[str, Any]] | None = None


def _duration(**kwargs: Any) -> dict[str, Any]:
    return {
        "device_class": SensorDeviceClass.DURATION,
        "native_unit_of_measurement": UnitOfTime.SECONDS,
        "suggested_unit_of_measurement": UnitOfTime.MINUTES,
        **kwargs,
    }


def _watching_on(state: AdminState, profile: Profile) -> str | None:
    """Where this kid is watching: the TV's name or the browser label; None when not watching."""
    session = session_for_profile(state, profile.id)
    return session.label if session else None


def _watching_on_attrs(state: AdminState, profile: Profile) -> dict[str, Any]:
    session = session_for_profile(state, profile.id)
    return {"target": session.target if session else None, "state": session.state if session else None}


def _sessions_attrs(state: AdminState) -> dict[str, Any]:
    return {"sessions": [
        {"target": x.target, "label": x.label, "state": x.state, "show_id": x.show_id, "episode_id": x.episode_id,
         "profile_ids": list(x.profile_ids)}
        for x in state.sessions
    ]}


def _queue(state: AdminState) -> int:
    return state.jobs.queued + state.jobs.running


SENSORS: tuple[TellyboxSensorDescription, ...] = (
    TellyboxSensorDescription(
        key="now_playing_show",
        translation_key="now_playing_show",
        value_fn=lambda s: s.now_playing.show if s.now_playing else None,
        attrs_fn=lambda s: {"show_id": s.now_playing.show_id, "episode_id": s.now_playing.episode_id}
        if s.now_playing
        else {},
    ),
    TellyboxSensorDescription(
        key="now_playing_episode",
        translation_key="now_playing_episode",
        value_fn=lambda s: s.now_playing.title if s.now_playing else None,
        attrs_fn=lambda s: {"show_id": s.now_playing.show_id, "episode_id": s.now_playing.episode_id}
        if s.now_playing
        else {},
    ),
    TellyboxSensorDescription(
        key="time_left",
        translation_key="time_left",
        value_fn=lambda s: s.group.remaining_s,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxSensorDescription(
        key="downloads_awaiting_approval",
        translation_key="downloads_awaiting_approval",
        value_fn=lambda s: s.jobs.held_ready,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TellyboxSensorDescription(
        key="download_queue",
        translation_key="download_queue",
        value_fn=_queue,
        attrs_fn=lambda s: {"failed": s.jobs.failed},
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TellyboxSensorDescription(
        key="inbox_pending",
        translation_key="inbox_pending",
        value_fn=lambda s: s.inbox.pending,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TellyboxSensorDescription(
        key="inbox_unhealthy",
        translation_key="inbox_unhealthy",
        value_fn=lambda s: s.inbox.unhealthy,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TellyboxSensorDescription(
        key="inbox_latest_received",
        translation_key="inbox_latest_received",
        value_fn=lambda s: s.inbox.latest_received_at,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TellyboxSensorDescription(
        key="active_sessions",
        translation_key="active_sessions",
        value_fn=lambda s: len(s.sessions),
        attrs_fn=_sessions_attrs,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TellyboxSensorDescription(
        key="time_up_reason",
        translation_key="time_up_reason",
        value_fn=lambda s: s.group.reason,
        device_class=SensorDeviceClass.ENUM,
        options=["allowance", "session_max", "blocked"],
    ),
    TellyboxSensorDescription(
        key="playback_action",
        translation_key="playback_action",
        value_fn=lambda s: s.group.action,
        device_class=SensorDeviceClass.ENUM,
        options=["continue", "finish_then_stop", "stop_now"],
    ),
    TellyboxSensorDescription(
        key="next_reset",
        translation_key="next_reset",
        value_fn=lambda s: s.day.resets_at,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TellyboxSensorDescription(
        key="media_disk_use",
        translation_key="media_disk_use",
        value_fn=lambda s: round(s.disk.media_bytes / 1_000_000_000, 2),
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

PROFILE_SENSORS: tuple[TellyboxProfileSensorDescription, ...] = (
    TellyboxProfileSensorDescription(
        key="time_left",
        translation_key="time_left",
        value_fn=lambda p: p.remaining_s,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxProfileSensorDescription(
        key="time_used_today",
        translation_key="time_used_today",
        value_fn=lambda p: p.used_s,
        **_duration(state_class=SensorStateClass.TOTAL_INCREASING),
    ),
    TellyboxProfileSensorDescription(
        key="allowance_today",
        translation_key="allowance_today",
        value_fn=lambda p: None if p.allowance_s is None else p.allowance_s + (p.extra_s or 0),
        entity_category=EntityCategory.DIAGNOSTIC,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxProfileSensorDescription(
        key="session_time",
        translation_key="session_time",
        value_fn=lambda p: p.session_elapsed_s,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxProfileSensorDescription(
        key="max_session",
        translation_key="max_session",
        value_fn=lambda p: p.max_session_s,
        entity_category=EntityCategory.DIAGNOSTIC,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxProfileSensorDescription(
        key="allowance_source",
        translation_key="allowance_source",
        value_fn=lambda p: p.allowance_source,
        device_class=SensorDeviceClass.ENUM,
        options=["inherit", "custom", "unlimited"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TellyboxProfileSensorDescription(
        key="ui_mode",  # HA-11: the kid app style; None while an older Tellybox doesn't say
        translation_key="ui_mode",
        value_fn=lambda p: p.ui_mode,
        device_class=SensorDeviceClass.ENUM,
        options=["icons", "text"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TellyboxProfileSensorDescription(
        key="max_session_source",
        translation_key="max_session_source",
        value_fn=lambda p: p.max_session_source,
        device_class=SensorDeviceClass.ENUM,
        options=["inherit", "custom", "unlimited"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TellyboxProfileSensorDescription(
        key="visible_shows",
        translation_key="visible_shows",
        value_fn=lambda p: p.visible_shows,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TellyboxProfileSensorDescription(
        key="watching_on",
        translation_key="watching_on",
        state_value_fn=_watching_on,
        attrs_fn=_watching_on_attrs,
    ),
)


def _yesterday(usage: ProfileUsage | None) -> int | None:
    """Index 0 is today, 1 is yesterday (the server's timer day); None when the list doesn't reach it."""
    return usage.days[1].used_s if usage is not None and len(usage.days) > 1 else None


def _average_7d(usage: ProfileUsage | None) -> int | None:
    """The seven completed days before today, zeros included for days not returned, rounded to a second."""
    if usage is None:
        return None
    return round(sum(d.used_s for d in usage.days[1:8]) / 7)


def _last_watched(usage: ProfileUsage | None) -> datetime | None:
    last = usage.last_watched if usage is not None else None
    return (last.ended_at or last.started_at) if last is not None else None


def _last_watched_attrs(usage: ProfileUsage | None) -> dict[str, Any]:
    last = usage.last_watched if usage is not None else None
    if last is None:
        return {}
    return {"episode_title": last.title, "show": last.show, "target": last.target}


HISTORY_SENSORS: tuple[TellyboxHistorySensorDescription, ...] = (
    TellyboxHistorySensorDescription(
        key="time_used_yesterday",
        translation_key="time_used_yesterday",
        value_fn=_yesterday,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxHistorySensorDescription(
        key="time_used_7d_average",
        translation_key="time_used_7d_average",
        value_fn=_average_7d,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxHistorySensorDescription(
        key="last_watched",
        translation_key="last_watched",
        value_fn=_last_watched,
        attrs_fn=_last_watched_attrs,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


class TellyboxSensor(TellyboxEntity, SensorEntity):
    entity_description: TellyboxSensorDescription

    @property
    def native_value(self) -> int | float | str | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None


class TellyboxProfileSensor(TellyboxProfileEntity, SensorEntity):
    entity_description: TellyboxProfileSensorDescription

    @property
    def native_value(self) -> int | float | str | None:
        profile = self.profile
        if profile is None:
            return None
        description = self.entity_description
        if description.state_value_fn:
            return description.state_value_fn(self.coordinator.data, profile)
        return description.value_fn(profile)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        fn = self.entity_description.attrs_fn
        profile = self.profile
        if fn is None or profile is None:
            return None
        return fn(self.coordinator.data, profile)


class TellyboxHistorySensor(TellyboxProfileEntity, SensorEntity):
    """A kid's history sensor. Follows the main coordinator for the kid's availability and the history
    coordinator for its data; it is available only while the last history update succeeded."""

    entity_description: TellyboxHistorySensorDescription

    def __init__(
        self, coordinator: TellyboxCoordinator, history: TellyboxHistoryCoordinator,
        description: TellyboxHistorySensorDescription, profile_id: int,
    ) -> None:
        super().__init__(coordinator, description, profile_id)
        self._history = history

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._history.async_add_listener(self._handle_history_update))

    @callback
    def _handle_history_update(self) -> None:
        self.async_write_ha_state()

    @property
    def usage(self) -> ProfileUsage | None:
        """This kid's entry in the history, looked up by id (the list's order is not relied on)."""
        data = self._history.data
        return next((p for p in data.profiles if p.id == self.profile_id), None) if data else None

    @property
    def available(self) -> bool:
        return super().available and self._history.last_update_success

    @property
    def native_value(self) -> int | float | datetime | None:
        return self.entity_description.value_fn(self.usage)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.usage) if fn else None


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: TellyboxCoordinator = entry.runtime_data.coordinator
    async_add_entities(TellyboxSensor(coordinator, d) for d in SENSORS)

    def factory(profile_id: int) -> list[Entity]:
        return [TellyboxProfileSensor(coordinator, d, profile_id) for d in PROFILE_SENSORS]

    entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, factory))

    history = entry.runtime_data.history
    if history is not None:
        def history_factory(profile_id: int) -> list[Entity]:
            return [TellyboxHistorySensor(coordinator, history, d, profile_id) for d in HISTORY_SENSORS]

        entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, history_factory))
    await async_setup_session_sensors(hass, entry, coordinator, async_add_entities)
