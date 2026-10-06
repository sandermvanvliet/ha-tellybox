"""Browse and play helpers shared by the Tellybox media players."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import BrowseMedia, MediaClass, MediaType
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import TellyboxCoordinator

SHOW = "show"
EPISODE = "episode"


def parse_media_id(media_id: str) -> tuple[str, int]:
    """`show:2` or `episode:4` (a bare number is an episode id)."""
    kind, _, number = media_id.rpartition(":")
    try:
        return kind or EPISODE, int(number)
    except ValueError as err:
        raise BrowseError(f"Unknown media id: {media_id}") from err


def episode_browse_item(url: Any, tile: Any) -> BrowseMedia:
    return BrowseMedia(
        media_class=MediaClass.EPISODE,
        media_content_id=f"{EPISODE}:{tile.episode_id}",
        media_content_type=MediaType.EPISODE,
        title=tile.title or f"Episode {tile.episode_id}",
        can_play=True,
        can_expand=False,
        thumbnail=url(tile.thumb),
    )


async def browse(
    client: Any, media_content_id: str | None, profile_ids: list[int] | None, root_title: str
) -> BrowseMedia:
    """The library root, or one show's episodes, as seen by the given kids (None means unfiltered)."""
    if media_content_id and media_content_id.startswith(f"{SHOW}:"):
        _, show_id = parse_media_id(media_content_id)
        show = await client.show(show_id, profile_ids)
        return BrowseMedia(
            media_class=MediaClass.TV_SHOW,
            media_content_id=f"{SHOW}:{show.show_id}",
            media_content_type=MediaType.TVSHOW,
            title=show.title,
            can_play=False,
            can_expand=True,
            thumbnail=client.url(show.artwork),
            children=[episode_browse_item(client.url, t) for t in show.episodes],
        )
    home = await client.home(profile_ids)
    children = [episode_browse_item(client.url, t) for t in home.continue_watching]
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
        title=root_title,
        can_play=False,
        can_expand=True,
        children=children,
    )


async def play_for(coordinator: TellyboxCoordinator, media_id: str, profile_ids: list[int]) -> None:
    """Start an episode for the given kids through the kid API (a time-up refusal is never forced)."""
    kind, number = parse_media_id(media_id)
    if kind != EPISODE:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="request",
                                 translation_placeholders={"detail": "choose an episode, not a show"})
    if not profile_ids:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_kids")
    await coordinator.async_command(lambda: coordinator.client.play(number, profile_ids))
