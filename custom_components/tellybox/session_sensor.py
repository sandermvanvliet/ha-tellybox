"""One sensor per in-app (browser) playback, created when the session appears and removed after it is gone.

The unique id is `{instance_id}_session_{device_id}`, so it survives episode changes and later sessions of the
same browser. The browser's device id only ever appears in the unique id, never in an attribute or a log line.
The TV session has no sensor here: the media player is the TV.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytellybox import Session

from .const import DOMAIN, MANUFACTURER, main_device_identifier
from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .sessions import device_sessions

REMOVE_AFTER_S = 30  # covers the autoplay hand-over and a flaky heartbeat


class TellyboxSessionSensor(CoordinatorEntity[TellyboxCoordinator], SensorEntity):
    """The state of one browser's playback; available only while the session is in the admin state."""

    _attr_has_entity_name = True
    _attr_translation_key = "device_session"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["loading", "playing", "paused", "buffering"]
    _unrecorded_attributes = frozenset({"position_s", "duration_s", "title"})

    def __init__(self, coordinator: TellyboxCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        iid = coordinator.instance_id
        self._attr_unique_id = f"{iid}_session_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={main_device_identifier(iid)},
            manufacturer=MANUFACTURER,
            name="Tellybox",
            sw_version=coordinator.data.version if coordinator.data else None,
            configuration_url=coordinator.client.url("/admin"),
        )
        self._last_label = "browser"

    @property
    def session(self) -> Session | None:
        data = self.coordinator.data
        return device_sessions(data).get(self._device_id) if data else None

    @property
    def available(self) -> bool:
        return super().available and self.session is not None

    @property
    def translation_placeholders(self) -> dict[str, str]:
        session = self.session
        if session is not None and session.label:
            self._last_label = session.label
        return {"label": self._last_label}

    @property
    def native_value(self) -> str | None:
        session = self.session
        return session.state if session else None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        session = self.session
        data = self.coordinator.data
        if session is None or data is None:
            return None
        kids = [p.name for pid in session.profile_ids if (p := data.profile(pid)) is not None]
        return {
            "label": session.label,
            "title": session.title,
            "show_id": session.show_id,
            "episode_id": session.episode_id,
            "kids": kids,
            "profile_ids": list(session.profile_ids),
            "position_s": session.position_s,
            "duration_s": session.duration_s,
        }


async def async_setup_session_sensors(
    hass: HomeAssistant,
    entry: TellyboxConfigEntry,
    coordinator: TellyboxCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sweep leftovers, add a sensor for each browser session now and later, remove them 30 s after they end."""
    registry = er.async_get(hass)
    prefix = f"{coordinator.instance_id}_session_"

    def unique_id(device_id: str) -> str:
        return prefix + device_id

    first = device_sessions(coordinator.data) if coordinator.data else {}
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain == "sensor" and reg_entry.unique_id.startswith(prefix) \
                and reg_entry.unique_id.removeprefix(prefix) not in first:
            registry.async_remove(reg_entry.entity_id)

    added: set[str] = set()  # device ids whose entity this run created
    pending: dict[str, CALLBACK_TYPE] = {}  # device id -> cancel of its scheduled removal

    def _remove_later(device_id: str) -> None:
        @callback
        def _remove(_now: Any) -> None:
            pending.pop(device_id, None)
            added.discard(device_id)
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id(device_id))
            if entity_id:
                registry.async_remove(entity_id)

        pending[device_id] = async_call_later(hass, REMOVE_AFTER_S, _remove)

    @callback
    def _update() -> None:
        if coordinator.data is None:
            return
        current = device_sessions(coordinator.data)
        new: list[TellyboxSessionSensor] = []
        for device_id in current:
            if (cancel := pending.pop(device_id, None)) is not None:
                cancel()
            if device_id in added:
                continue
            reg_entry = registry.async_get(registry.async_get_entity_id("sensor", DOMAIN, unique_id(device_id)) or "")
            if reg_entry is not None and reg_entry.disabled:
                continue  # the user disabled it: never re-create
            added.add(device_id)
            new.append(TellyboxSessionSensor(coordinator, device_id))
        if new:
            async_add_entities(new)
        for device_id in added - current.keys():
            if device_id not in pending:
                _remove_later(device_id)

    @callback
    def _cancel_pending() -> None:
        for cancel in pending.values():
            cancel()
        pending.clear()

    _update()
    entry.async_on_unload(coordinator.async_add_listener(_update))
    entry.async_on_unload(_cancel_pending)
