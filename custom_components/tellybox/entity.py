"""Entity base classes and the device layout.

Devices: one Tellybox device per server (identifier: the instance id), and one device per kid profile,
`via_device` the Tellybox device. Unique ids: `{instance_id}_{key}` on the Tellybox device and
`{instance_id}_profile_{profile_id}_{key}` on a kid's device. Every entity has a translated name
(`has_entity_name`, `translation_key = key`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytellybox import Profile

from .const import MANUFACTURER, main_device_identifier, profile_device_identifier
from .coordinator import TellyboxCoordinator


class TellyboxEntity(CoordinatorEntity[TellyboxCoordinator]):
    """An entity on the Tellybox device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TellyboxCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        iid = coordinator.instance_id
        self._attr_unique_id = f"{iid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={main_device_identifier(iid)},
            manufacturer=MANUFACTURER,
            name="Tellybox",
            sw_version=coordinator.data.version if coordinator.data else None,
            configuration_url=coordinator.client.url("/admin"),
        )


class TellyboxProfileEntity(CoordinatorEntity[TellyboxCoordinator]):
    """An entity on a kid's device. Unavailable while the profile is missing from the state."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TellyboxCoordinator, description: EntityDescription, profile_id: int) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.profile_id = profile_id
        iid = coordinator.instance_id
        self._attr_unique_id = f"{iid}_profile_{profile_id}_{description.key}"
        profile = self.profile
        self._attr_device_info = DeviceInfo(
            identifiers={profile_device_identifier(iid, profile_id)},
            manufacturer=MANUFACTURER,
            model="Kid profile",
            name=profile.name if profile else f"Kid {profile_id}",
            via_device=main_device_identifier(iid),
        )

    @property
    def profile(self) -> Profile | None:
        data = self.coordinator.data
        return data.profile(self.profile_id) if data else None

    @property
    def available(self) -> bool:
        return super().available and self.profile is not None


def add_profile_entities(
    coordinator: TellyboxCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[int], Iterable[Entity]],
) -> Callable[[], None]:
    """Add `factory(profile_id)` for every kid now, and again for each kid that appears later.

    Returns the listener's remover; platforms pass it to `entry.async_on_unload`. Removing a deleted kid's
    device is the integration's job (`__init__.py`), not the platform's.
    """
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        if coordinator.data is None:
            return
        new = [p.id for p in coordinator.data.profiles if p.id not in known]
        if not new:
            return
        known.update(new)
        async_add_entities([entity for pid in new for entity in factory(pid)])

    _add_new()
    return coordinator.async_add_listener(_add_new)
