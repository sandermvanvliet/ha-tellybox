"""Device triggers: the `tellybox_event` bus events, offered per device in the automation editor."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .events import EVENT_NAME, PROFILE_EVENT_TYPES, SERVER_EVENT_TYPES

TRIGGER_TYPES = frozenset(PROFILE_EVENT_TYPES) | frozenset(SERVER_EVENT_TYPES)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES)})


def _types_for_device(hass: HomeAssistant, device_id: str) -> tuple[str, ...]:
    """The event types a device can raise: kid devices and the Tellybox device differ, foreign ones have none."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return ()
    for domain, ident in device.identifiers:
        if domain != DOMAIN:
            continue
        # Kid devices are `{instance_id}_profile_{id}`; the Tellybox device is the bare instance id.
        return PROFILE_EVENT_TYPES if "_profile_" in ident else SERVER_EVENT_TYPES
    return ()


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """List the device triggers for a Tellybox device."""
    return [
        {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id, CONF_TYPE: event_type}
        for event_type in _types_for_device(hass, device_id)
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Fire the action on a `tellybox_event` for this device and type."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_NAME,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(hass, event_config, action, trigger_info, platform_type="device")
