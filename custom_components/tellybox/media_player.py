"""The Tellybox media player: what plays on the TV, browse the approved library, play for kids.

Playing goes through the kid API, so a time-up refusal (409) is respected and never forced.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxEntity, TellyboxProfileEntity, add_profile_entities
from .media_common import EPISODE, browse, play_for
from .sessions import session_for_profile

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


@dataclass(frozen=True)
class _NowPlayingSession:
    """A session-like view of `now_playing`, for a server that sends no `sessions`."""

    episode_id: int
    title: str
    state: str
    position_s: int | None
    duration_s: int | None
    show: str | None
    target: str = "tv"
    label: str = ""


class TellyboxKidMediaPlayer(TellyboxProfileEntity, MediaPlayerEntity):
    """One kid's player: what that kid watches, browse what that kid may see, play for that kid only.

    No pause, play or stop: Tellybox's are household-wide, so they would act on other kids' playback too.
    """

    _attr_name = None
    _attr_media_content_type = MediaType.EPISODE
    _attr_media_image_remotely_accessible = False  # a LAN address; Home Assistant fetches and proxies it
    _attr_supported_features = MediaPlayerEntityFeature.BROWSE_MEDIA | MediaPlayerEntityFeature.PLAY_MEDIA
    _attr_media_position_updated_at: datetime | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_media_position_updated_at = dt_util.utcnow()
        super()._handle_coordinator_update()

    def _session(self) -> Any | None:
        data = self.coordinator.data
        if data is None:
            return None
        if (session := session_for_profile(data, self.profile_id)) is not None:
            return session
        playing = data.now_playing
        if playing is not None and self.profile_id in playing.profile_ids:
            return _NowPlayingSession(
                playing.episode_id, playing.title, playing.state, playing.position_s, playing.duration_s, playing.show
            )
        return None

    @property
    def state(self) -> MediaPlayerState:
        session = self._session()
        in_app = session is not None and session.target == "device"
        if not in_app and not self.coordinator.data.tv.reachable:
            return MediaPlayerState.OFF
        if session is None:
            return MediaPlayerState.IDLE
        if session.state == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.PLAYING  # playing, buffering and loading

    @property
    def media_content_id(self) -> str | None:
        session = self._session()
        return f"{EPISODE}:{session.episode_id}" if session else None

    @property
    def media_title(self) -> str | None:
        session = self._session()
        return session.title if session else None

    @property
    def media_series_title(self) -> str | None:
        session = self._session()
        return getattr(session, "show", None) if session else None  # only `now_playing` knows the show title

    @property
    def media_duration(self) -> int | None:
        session = self._session()
        return session.duration_s if session else None

    @property
    def media_position(self) -> int | None:
        session = self._session()
        return session.position_s if session else None

    @property
    def media_image_url(self) -> str | None:
        session = self._session()
        return self.coordinator.client.url(f"/img/episode/{session.episode_id}.jpg") if session else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        session = self._session()
        return {"watching_on": session.label} if session and session.label else {}

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        # Always the TV, for this kid only; Tellybox refuses (409) when the kid is out of time.
        await play_for(self.coordinator, media_id, [self.profile_id])

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        profile = self.profile
        title = profile.name if profile else f"Kid {self.profile_id}"
        return await browse(self.coordinator.client, media_content_id, [self.profile_id], title)


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([TellyboxMediaPlayer(coordinator)])

    def factory(profile_id: int) -> list[Entity]:
        return [TellyboxKidMediaPlayer(coordinator, PLAYER, profile_id)]

    entry.async_on_unload(add_profile_entities(coordinator, async_add_entities, factory))
