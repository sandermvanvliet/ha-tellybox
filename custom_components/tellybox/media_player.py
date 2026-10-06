"""The Tellybox media player: what plays on the TV, browse the approved library, play for kids.

Playing goes through the kid API, so a time-up refusal (409) is respected and never forced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxEntity
from .media_common import EPISODE, browse, play_for

PARALLEL_UPDATES = 1

PLAYER = MediaPlayerEntityDescription(key="player")

class TellyboxMediaPlayer(TellyboxEntity, MediaPlayerEntity):
    """Named after the device (no entity name)."""

    _attr_name = None

    _attr_media_content_type = MediaType.EPISODE
    _attr_media_position_updated_at: datetime | None = None

    def __init__(self, coordinator: TellyboxCoordinator) -> None:
        super().__init__(coordinator, PLAYER)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_media_position_updated_at = dt_util.utcnow()
        super()._handle_coordinator_update()

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )
        if self.coordinator.control:
            features |= MediaPlayerEntityFeature.STOP
        return features

    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data
        if not data.tv.reachable:
            return MediaPlayerState.OFF
        playing = data.now_playing
        if playing is None:
            return MediaPlayerState.IDLE
        if playing.state == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.PLAYING  # playing, buffering and loading

    @property
    def media_content_id(self) -> str | None:
        playing = self.coordinator.data.now_playing
        return f"{EPISODE}:{playing.episode_id}" if playing else None

    @property
    def media_title(self) -> str | None:
        playing = self.coordinator.data.now_playing
        return playing.title if playing else None

    @property
    def media_series_title(self) -> str | None:
        playing = self.coordinator.data.now_playing
        return playing.show if playing else None

    @property
    def media_duration(self) -> int | None:
        playing = self.coordinator.data.now_playing
        return playing.duration_s if playing else None

    @property
    def media_position(self) -> int | None:
        playing = self.coordinator.data.now_playing
        return playing.position_s if playing else None

    @property
    def media_image_url(self) -> str | None:
        playing = self.coordinator.data.now_playing
        return self.coordinator.client.url(playing.thumb_path) if playing else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return False  # the address is a LAN one; Home Assistant fetches and proxies it

    async def async_media_pause(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.pause)

    async def async_media_play(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.resume)

    async def async_media_stop(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.stop_now)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        coordinator = self.coordinator
        kids = list(coordinator.last_watchers) or [p.id for p in coordinator.data.profiles]
        await play_for(coordinator, media_id, kids)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        kids = list(self.coordinator.last_watchers) or None
        return await browse(self.coordinator.client, media_content_id, kids, "Tellybox")


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([TellyboxMediaPlayer(entry.runtime_data.coordinator)])
