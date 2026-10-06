"""Binary sensors: the group's time state and the TV, and each kid's status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pytellybox import AdminState, Profile

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxEntity, TellyboxProfileEntity, add_profile_entities

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TellyboxBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[AdminState], bool]


@dataclass(frozen=True, kw_only=True)
class TellyboxProfileBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[Profile], bool | None]


BINARY_SENSORS: tuple[TellyboxBinarySensorDescription, ...] = (
    TellyboxBinarySensorDescription(key="time_up", translation_key="time_up", value_fn=lambda s: s.group.time_up),
    TellyboxBinarySensorDescription(
        key="last_five_minutes", translation_key="last_five_minutes", value_fn=lambda s: s.group.last_five
    ),
    TellyboxBinarySensorDescription(
        key="tv_reachable",
        translation_key="tv_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.tv.reachable,
    ),
)

PROFILE_BINARY_SENSORS: tuple[TellyboxProfileBinarySensorDescription, ...] = (
    TellyboxProfileBinarySensorDescription(key="watching", translation_key="watching", value_fn=lambda p: p.watching),
    TellyboxProfileBinarySensorDescription(key="time_up", translation_key="time_up", value_fn=lambda p: p.time_up),
    TellyboxProfileBinarySensorDescription(
        key="last_five_minutes", translation_key="last_five_minutes", value_fn=lambda p: p.last_five
    ),
    TellyboxProfileBinarySensorDescription(
        key="no_visible_shows",  # HA-10: an empty kid app; None while an older Tellybox doesn't say
        translation_key="no_visible_shows",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda p: None if p.visible_shows is None else p.visible_shows == 0,
    ),
    TellyboxProfileBinarySensorDescription(
        key="watch_in_app",  # HA-11: may the kid watch in the browser app; None while an older Tellybox doesn't say
        translation_key="watch_in_app",
        value_fn=lambda p: p.watch_in_app,
    ),
    TellyboxProfileBinarySensorDescription(key="blocked", translation_key="blocked", value_fn=lambda p: p.blocked),
    TellyboxProfileBinarySensorDescription(
        key="unlimited", translation_key="unlimited", value_fn=lambda p: p.unlimited
    ),
)


class TellyboxBinarySensor(TellyboxEntity, BinarySensorEntity):
    entity_description: TellyboxBinarySensorDescription

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)


class TellyboxProfileBinarySensor(TellyboxProfileEntity, BinarySensorEntity):
    entity_description: TellyboxProfileBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        profile = self.profile
        return self.entity_description.value_fn(profile) if profile else None


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: TellyboxCoordinator = entry.runtime_data.coordinator
    async_add_entities(TellyboxBinarySensor(coordinator, d) for d in BINARY_SENSORS)

    def factory(profile_id: int) -> list[Entity]:
        return [TellyboxProfileBinarySensor(coordinator, d, profile_id) for d in PROFILE_BINARY_SENSORS]

    entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, factory))
