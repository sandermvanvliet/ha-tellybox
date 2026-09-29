"""Sensors: the Tellybox device (now playing, time left, downloads, disk) and each kid's time."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pytellybox import AdminState, Profile

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxEntity, TellyboxProfileEntity, add_profile_entities

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TellyboxSensorDescription(SensorEntityDescription):
    """A sensor on the Tellybox device."""

    value_fn: Callable[[AdminState], int | float | str | None]
    attrs_fn: Callable[[AdminState], Mapping[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class TellyboxProfileSensorDescription(SensorEntityDescription):
    """A sensor on a kid's device."""

    value_fn: Callable[[Profile], int | float | str | None]


def _duration(**kwargs: Any) -> dict[str, Any]:
    return {
        "device_class": SensorDeviceClass.DURATION,
        "native_unit_of_measurement": UnitOfTime.SECONDS,
        "suggested_unit_of_measurement": UnitOfTime.MINUTES,
        **kwargs,
    }


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
        value_fn=lambda p: p.allowance_s + (p.extra_s or 0),
        entity_category=EntityCategory.DIAGNOSTIC,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
    TellyboxProfileSensorDescription(
        key="session_time",
        translation_key="session_time",
        value_fn=lambda p: p.session_elapsed_s,
        **_duration(state_class=SensorStateClass.MEASUREMENT),
    ),
)


class TellyboxSensor(TellyboxEntity, SensorEntity):
    entity_description: TellyboxSensorDescription

    @property
    def native_value(self) -> int | float | str | None:
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
        return self.entity_description.value_fn(profile) if profile else None


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: TellyboxCoordinator = entry.runtime_data.coordinator
    async_add_entities(TellyboxSensor(coordinator, d) for d in SENSORS)

    def factory(profile_id: int) -> list[Entity]:
        return [TellyboxProfileSensor(coordinator, d, profile_id) for d in PROFILE_SENSORS]

    entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, factory))
