"""The Tellybox integration: live state and parent controls for a Tellybox server."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from pytellybox import EXTRA_MINUTES_MAX, TellyboxClient  # noqa: F401  (tests patch TellyboxClient here)

from .const import (
    ATTR_EPISODE_ID,
    ATTR_MINUTES,
    CONF_TOKEN,
    CONF_URL,
    DOMAIN,
    SERVICE_ADD_TIME,
    SERVICE_BLOCK_TODAY,
    SERVICE_CLEAR_OVERRIDES,
    SERVICE_PLAY_EPISODE,
    SERVICE_SET_UNLIMITED_TODAY,
    SERVICE_STOP_NOW,
    main_device_identifier,
)
from .coordinator import TellyboxConfigEntry, TellyboxCoordinator, TellyboxData

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.MEDIA_PLAYER, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_DEVICE_IDS = {vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1))}
_OVERRIDE_SCHEMA = vol.Schema(_DEVICE_IDS)
_SCHEMAS = {
    SERVICE_ADD_TIME: vol.Schema({**_DEVICE_IDS, vol.Required(ATTR_MINUTES): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=EXTRA_MINUTES_MAX))}),
    SERVICE_SET_UNLIMITED_TODAY: _OVERRIDE_SCHEMA,
    SERVICE_BLOCK_TODAY: _OVERRIDE_SCHEMA,
    SERVICE_CLEAR_OVERRIDES: _OVERRIDE_SCHEMA,
    SERVICE_STOP_NOW: _OVERRIDE_SCHEMA,
    SERVICE_PLAY_EPISODE: vol.Schema({**_DEVICE_IDS, vol.Required(ATTR_EPISODE_ID): vol.All(
        vol.Coerce(int), vol.Range(min=1))}),
}


def _resolve_targets(hass: HomeAssistant, device_ids: list[str]) -> tuple[TellyboxCoordinator, list[int] | None]:
    """Turn `device_id`s into (coordinator, profile ids). The Tellybox device means everyone (None), a kid's
    device means that kid. A mix, several servers or a foreign device is refused."""
    registry = dr.async_get(hass)
    coordinator: TellyboxCoordinator | None = None
    everyone = False
    profile_ids: list[int] = []
    for device_id in device_ids:
        device = registry.async_get(device_id)
        entry = None
        for entry_id in device.config_entries if device else ():
            candidate = hass.config_entries.async_get_entry(entry_id)
            if candidate is not None and candidate.domain == DOMAIN and candidate.runtime_data is not None:
                entry = candidate
                break
        if device is None or entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_target",
                translation_placeholders={"device": device_id},
            )
        target = entry.runtime_data.coordinator
        if coordinator is not None and coordinator is not target:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="multiple_servers")
        coordinator = target
        main = main_device_identifier(target.instance_id)
        prefix = f"{target.instance_id}_profile_"
        for domain, ident in device.identifiers:
            if domain != DOMAIN:
                continue
            if (domain, ident) == main:
                everyone = True
            elif ident.startswith(prefix) and ident[len(prefix):].isdigit():
                profile_ids.append(int(ident[len(prefix):]))
    assert coordinator is not None
    if everyone and profile_ids:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="mixed_targets")
    if everyone:
        return coordinator, None
    if not profile_ids:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_target", translation_placeholders={"device": ""}
        )
    return coordinator, sorted(set(profile_ids))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions once, for every Tellybox."""

    async def handle(call: ServiceCall) -> None:
        coordinator, profile_ids = _resolve_targets(hass, call.data["device_id"])
        client = coordinator.client
        if call.service == SERVICE_PLAY_EPISODE:
            kids = profile_ids if profile_ids is not None else list(coordinator.last_watchers)
            if not kids:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_kids")
            episode_id = call.data[ATTR_EPISODE_ID]
            await coordinator.async_command(lambda: client.play(episode_id, kids))
            return
        if not coordinator.control:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="control_disabled")
        if call.service == SERVICE_ADD_TIME:
            minutes = call.data[ATTR_MINUTES]
            await coordinator.async_command(lambda: client.add_time(minutes, profile_ids))
        elif call.service == SERVICE_SET_UNLIMITED_TODAY:
            await coordinator.async_command(lambda: client.set_unlimited(profile_ids))
        elif call.service == SERVICE_BLOCK_TODAY:
            await coordinator.async_command(lambda: client.block(profile_ids))
        elif call.service == SERVICE_CLEAR_OVERRIDES:
            await coordinator.async_command(lambda: client.clear_today(profile_ids))
        elif call.service == SERVICE_STOP_NOW:
            # Stopping the TV is not per kid, so any Tellybox or kid device stops what is playing.
            await coordinator.async_command(client.stop_now)

    for name, schema in _SCHEMAS.items():
        hass.services.async_register(DOMAIN, name, handle, schema=schema)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TellyboxConfigEntry) -> bool:
    """Create the client (HA's shared aiohttp session), the coordinator (first refresh, then start the event
    stream), set `entry.runtime_data`, forward PLATFORMS, reload on options change, and remove the devices of
    kids that no longer exist whenever the state changes."""
    client = TellyboxClient(entry.data[CONF_URL], entry.data[CONF_TOKEN], async_get_clientsession(hass))
    coordinator = TellyboxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = TellyboxData(client=client, coordinator=coordinator)

    @callback
    def _remove_gone_kids() -> None:
        if coordinator.data is None:
            return
        registry = dr.async_get(hass)
        prefix = f"{coordinator.instance_id}_profile_"
        alive = {p.id for p in coordinator.data.profiles}
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
            for domain, ident in device.identifiers:
                if domain == DOMAIN and ident.startswith(prefix) and ident[len(prefix):].isdigit():
                    if int(ident[len(prefix):]) not in alive:
                        registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)

    _remove_gone_kids()
    entry.async_on_unload(coordinator.async_add_listener(_remove_gone_kids))
    entry.async_on_unload(entry.add_update_listener(_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()
    return True


async def _options_updated(hass: HomeAssistant, entry: TellyboxConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TellyboxConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.async_stop()
    return unloaded
