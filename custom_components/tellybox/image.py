"""Image platform: each kid's picture (the uploaded photo, else the built-in avatar).

Home Assistant fetches the bytes itself and serves them through its image proxy, so the browser never sees
the Tellybox address. The bytes are cached: refetched when the source path changes and at most once an hour
otherwise (the photo's URL stays the same when it is replaced). `image_last_updated` only moves when the
content changes.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from pytellybox import TellyboxError

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxProfileEntity, add_profile_entities

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

REFRESH_INTERVAL = timedelta(hours=1)
RETRY_INTERVAL = timedelta(minutes=5)

PICTURE = EntityDescription(key="picture", translation_key="picture")


class TellyboxProfilePicture(TellyboxProfileEntity, ImageEntity):
    """A kid's photo or avatar."""

    def __init__(self, hass: HomeAssistant, coordinator: TellyboxCoordinator, profile_id: int) -> None:
        TellyboxProfileEntity.__init__(self, coordinator, PICTURE, profile_id)
        ImageEntity.__init__(self, hass)
        self._content: bytes | None = None
        self._digest: str | None = None
        self._fetched_source: str | None = None
        self._next_fetch: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def source_path(self) -> str | None:
        """Photo if the kid has one, else the avatar, else nothing."""
        profile = self.profile
        if profile is None:
            return None
        if profile.picture:
            return profile.picture
        if profile.avatar:
            return f"/static/avatars/{profile.avatar}.svg"
        return None

    @property
    def available(self) -> bool:
        return super().available and self.source_path is not None

    def _due(self, source: str | None) -> bool:
        if source is None:
            return False
        if source != self._fetched_source or self._next_fetch is None:
            return True
        return dt_util.utcnow() >= self._next_fetch

    async def _async_refresh(self, source: str) -> None:
        async with self._lock:
            if not self._due(source):  # another caller fetched while we waited
                return
            now = dt_util.utcnow()
            self._fetched_source = source
            try:
                image = await self.coordinator.client.image(source)
            except (TellyboxError, ValueError) as err:
                # Keep what we have; never put the address in a log line.
                _LOGGER.debug("Could not fetch the picture for profile %s (%s)", self.profile_id, type(err).__name__)
                self._next_fetch = now + RETRY_INTERVAL
                return
            self._next_fetch = now + REFRESH_INTERVAL
            digest = hashlib.sha256(image.content).hexdigest()
            self._attr_content_type = image.content_type
            changed = digest != self._digest
            self._content, self._digest = image.content, digest
            if changed:
                self._attr_image_last_updated = now
            if changed and self.hass is not None and self.entity_id:
                self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (source := self.source_path) is not None:
            await self._async_refresh(source)

    @callback
    def _handle_coordinator_update(self) -> None:
        source = self.source_path
        if self._due(source) and source is not None:
            self.hass.async_create_background_task(
                self._async_refresh(source), f"tellybox picture {self.profile_id}"
            )
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        if self._content is None and (source := self.source_path) is not None:
            self._next_fetch = None  # nothing cached: fetch now
            await self._async_refresh(source)
        return self._content


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: TellyboxCoordinator = entry.runtime_data.coordinator

    def factory(profile_id: int) -> list[Entity]:
        return [TellyboxProfilePicture(hass, coordinator, profile_id)]

    entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, factory))
