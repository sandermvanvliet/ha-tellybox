"""The Tellybox media player: what plays on the TV, browse the approved library, play for kids.

Playing goes through the kid API, so a time-up refusal (409) is respected and never forced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TellyboxConfigEntry, TellyboxCoordinator
from .entity import TellyboxEntity

PARALLEL_UPDATES = 1

PLAYER = MediaPlayerEntityDescription(key="player")

SHOW = "show"
EPISODE = "episode"


def _parse(media_id: str) -> tuple[str, int]:
    """`show:2` or `episode:4` (a bare number is an episode id)."""
    kind, _, number = media_id.rpartition(":")
    try:
        return kind or EPISODE, int(number)
    except ValueError as err:
        raise BrowseError(f"Unknown media id: {media_id}") from err


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
        kind, number = _parse(media_id)
        if kind != EPISODE:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="request",
                                     translation_placeholders={"detail": "choose an episode, not a show"})
        coordinator = self.coordinator
        kids = list(coordinator.last_watchers) or [p.id for p in coordinator.data.profiles]
        if not kids:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_kids")
        await coordinator.async_command(lambda: coordinator.client.play(number, kids))

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        client = self.coordinator.client
        kids = list(self.coordinator.last_watchers) or None
        if media_content_id and media_content_id.startswith(f"{SHOW}:"):
            _, show_id = _parse(media_content_id)
            show = await client.show(show_id, kids)
            return BrowseMedia(
                media_class=MediaClass.TV_SHOW,
                media_content_id=f"{SHOW}:{show.show_id}",
                media_content_type=MediaType.TVSHOW,
                title=show.title,
                can_play=False,
                can_expand=True,
                thumbnail=client.url(show.artwork),
                children=[_episode(client.url, t) for t in show.episodes],
            )
        home = await client.home(kids)
        children = [_episode(client.url, t) for t in home.continue_watching]
        children += [
            BrowseMedia(
                media_class=MediaClass.TV_SHOW,
                media_content_id=f"{SHOW}:{s.show_id}",
                media_content_type=MediaType.TVSHOW,
                title=s.title,
                can_play=False,
                can_expand=True,
                thumbnail=client.url(s.artwork),
            )
            for s in home.shows
        ]
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="library",
            title="Tellybox",
            can_play=False,
            can_expand=True,
            children=children,
        )


def _episode(url: Any, tile: Any) -> BrowseMedia:
    return BrowseMedia(
        media_class=MediaClass.EPISODE,
        media_content_id=f"{EPISODE}:{tile.episode_id}",
        media_content_type=MediaType.EPISODE,
        title=tile.title or f"Episode {tile.episode_id}",
        can_play=True,
        can_expand=False,
        thumbnail=url(tile.thumb),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: TellyboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([TellyboxMediaPlayer(entry.runtime_data.coordinator)])
