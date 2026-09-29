"""Override buttons for everyone (Tellybox device) and for each kid. Only with parent controls on."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pytellybox import TellyboxClient

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxEntity, TellyboxProfileEntity, add_profile_entities

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class TellyboxButtonDescription(ButtonEntityDescription):
    """`press_fn(client, profile_ids)`; `profile_ids` is None for everyone."""

    press_fn: Callable[[TellyboxClient, Sequence[int] | None], Awaitable[Any]]
    entity_registry_visible_default: bool = False


ADD_15 = TellyboxButtonDescription(
    key="add_15_minutes", translation_key="add_15_minutes", press_fn=lambda c, ids: c.add_time(15, ids)
)
ADD_30 = TellyboxButtonDescription(
    key="add_30_minutes", translation_key="add_30_minutes", press_fn=lambda c, ids: c.add_time(30, ids)
)
UNLIMITED = TellyboxButtonDescription(
    key="unlimited_today", translation_key="unlimited_today", press_fn=lambda c, ids: c.set_unlimited(ids)
)
BLOCK = TellyboxButtonDescription(
    key="block_today", translation_key="block_today", press_fn=lambda c, ids: c.block(ids)
)
CLEAR = TellyboxButtonDescription(
    key="clear_overrides", translation_key="clear_overrides", press_fn=lambda c, ids: c.clear_today(ids)
)
STOP_NOW = TellyboxButtonDescription(
    key="stop_now", translation_key="stop_now", press_fn=lambda c, ids: c.stop_now()
)

BUTTONS: tuple[TellyboxButtonDescription, ...] = (STOP_NOW, ADD_15, ADD_30, UNLIMITED, BLOCK, CLEAR)
PROFILE_BUTTONS: tuple[TellyboxButtonDescription, ...] = (ADD_15, ADD_30, UNLIMITED, BLOCK, CLEAR)


class TellyboxButton(TellyboxEntity, ButtonEntity):
    entity_description: TellyboxButtonDescription

    async def async_press(self) -> None:
        client = self.coordinator.client
        await self.coordinator.async_command(lambda: self.entity_description.press_fn(client, None))


class TellyboxProfileButton(TellyboxProfileEntity, ButtonEntity):
    entity_description: TellyboxButtonDescription

    async def async_press(self) -> None:
        client = self.coordinator.client
        await self.coordinator.async_command(lambda: self.entity_description.press_fn(client, [self.profile_id]))


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: TellyboxCoordinator = entry.runtime_data.coordinator
    if not coordinator.control:
        return
    async_add_entities(TellyboxButton(coordinator, d) for d in BUTTONS)

    def factory(profile_id: int) -> list[Entity]:
        return [TellyboxProfileButton(coordinator, d, profile_id) for d in PROFILE_BUTTONS]

    entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, factory))
