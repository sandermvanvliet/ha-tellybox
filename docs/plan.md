# Phase 1: the Tellybox integration for Home Assistant

Status: approved by the owner on 2026-09-29.

This is Phase 1 of the owner's plan "Tellybox × Home Assistant: upstream features & integration plan". Phase 0, the admin API in Tellybox (step 9, v2.1), is deployed; its contract is Tellybox's [`docs/admin-api.md`](https://github.com/sandermvanvliet/Tellybox/blob/main/docs/admin-api.md).

## Decisions (owner, 2026-09-29)

- **Two public repositories, both Apache-2.0:**
  - [`pytellybox`](https://github.com/sandermvanvliet/pytellybox): the async client, published to PyPI by trusted publishing from a `v*` tag;
  - `ha-tellybox` (this repository): installed through HACS.
- **Home Assistant 2026.4.0 or later**; the owner runs 2026.4.2. Tests run on HA's current test harness.
- **One device per kid**, alongside the Tellybox device. The original plan had this in Phase 3, but profiles have shipped.
- **Safety** (the Tellybox rules still hold):
  - every action goes through Tellybox;
  - playing uses the kid API, so a time-up 409 is respected and never forced;
  - the override buttons are hidden from auto-generated dashboards;
  - the README warns that HA's own Cast entity bypasses the timer.

## Contract (controller, done first)

- **`pytellybox`:**
  - `models.py` (complete) and `errors.py` (complete);
  - `client.py` with the signatures and behaviour in its docstrings, bodies not yet written;
  - `mock.py` described;
  - CI and the publish workflow.
- **`ha-tellybox`:**
  - `manifest.json`, `hacs.json`, `const.py` (the service names, backoff and device identifiers);
  - `entity.py` (complete: the base classes, the device layout, the unique ids, and `add_profile_entities`, which adds a kid's entities when the kid appears);
  - `coordinator.py` and `__init__.py` as contracts;
  - `strings.json` and `translations/en.json` with **every** key and English text;
  - `tests/conftest.py` (complete: `FakeTellyboxClient`, `patch_client`, `config_entry`, `setup_integration`).

## Part A: pytellybox (subagent A, repository `pytellybox`)

- **`TellyboxClient`**, per the docstrings:
  - aiohttp, with the caller's session;
  - the error mapping, with the token never in messages or logs;
  - an SSE parser that skips `:` comments, reads `data:` lines (multi-line data joined), uses EVENTS_READ_TIMEOUT_S, and raises TellyboxConnectionError when the stream ends;
  - `profile_ids` sent as a JSON list, or as `?profile_ids=1,3` for DELETE and `?profiles=` on the kid API;
  - `add_time` validates 1..240 before sending.
- **`mock.py`:** `MockTellybox` (an aiohttp app) and `python -m pytellybox.mock`, as described in the module.
- **Tests:**
  - `aiohttp.test_utils.TestServer` or `aioresponses`, covering every call and error;
  - SSE: the first event, keepalive, a multi-line event, the end of the stream, a 401 on connect;
  - the mock server end to end with the real client.

## Part B: setup, coordinator, actions, diagnostics (subagent B, `ha-tellybox`)

- **`coordinator.py`**, as described in the contract, including `async_command` with translated errors (`exceptions.*`).
- **`__init__.py`:**
  - setup and unload;
  - `entry.runtime_data`;
  - reload on an options change;
  - device cleanup: kids that disappear from the state lose their device (`device_registry.async_update_device(..., remove_config_entry_id=...)`).
- **`config_flow.py`:**
  - **User step:** the URL and token. It normalises the URL (a scheme is required, and the trailing slash is dropped), calls `info()` (not Tellybox: `not_tellybox`), then `state()` (`invalid_auth` on 401; every token has at least the `read` scope). It sets the unique id to `info.instance_id` and aborts if that is already configured. The title is "Tellybox".
  - **Reauth:** `reauth_confirm` asks for the token only. It aborts with `wrong_instance` if the instance id differs.
  - **Options flow:** CONF_CONTROL, default True.
- **Actions** (`services.yaml` and the handlers, registered once in `async_setup`):
  - add_time, set_unlimited_today, block_today, clear_overrides, stop_now, play_episode;
  - each resolves `device_id`s: the Tellybox device means everyone (`profile_ids=None`), a kid's device means that kid, and a mix is refused;
  - overrides need CONF_CONTROL (`control_disabled`);
  - play_episode uses the kids' devices, else `coordinator.last_watchers`, else `no_kids`.
- **`diagnostics.py`:** the entry data with the token and URL redacted, the options, and the last state's `raw`.
- **Tests:**
  - the config flow: success, cannot_connect, invalid_auth, not_tellybox, already_configured, reauth (success and wrong instance), options;
  - setup and unload;
  - the coordinator: the first refresh, an event updates the data, backoff after a broken stream, availability after UNAVAILABLE_AFTER_S (with `async_fire_time_changed` / freezer), a 401 starts reauth, `async_command` error mapping;
  - each action with device targets;
  - diagnostics redaction;
  - a deleted kid's device is removed.

## Part C: entities (subagent C, `ha-tellybox`)

Every entity uses the keys and names already in `strings.json`. Values come from `coordinator.data`, an `AdminState`.

**The Tellybox device** (`TellyboxEntity`):

| Key | Platform | Value and notes |
|---|---|---|
| `player` | media_player | Named after the device. The state is playing, paused (buffering and loading count as playing), idle when nothing plays, or off when the TV is unreachable. Title, series (show), `media_image_url` = `client.url(now_playing.thumb_path)`, duration and position. Supports PAUSE, PLAY, BROWSE_MEDIA and PLAY_MEDIA (the kid API, for `last_watchers` or every kid when there are none), plus STOP with control (`stop_now`). Browse: home, then the shows and continue watching, then a show's episodes; `media_content_id` is `show:2` or `episode:4`. A 409 raises the translated `time_up` error. |
| `now_playing_show`, `now_playing_episode` | sensor | Text, or None when nothing plays. Attributes: `show_id`, `episode_id`. |
| `time_left` | sensor | `group.remaining_s`. Duration device class, native unit seconds, suggested unit minutes. None when unlimited or unknown. |
| `downloads_awaiting_approval` | sensor | `jobs.held_ready`. |
| `download_queue` | sensor | `queued + running`, with attribute `failed`. |
| `media_disk_use` | sensor | `disk.media_bytes` in GB (data size). Diagnostic, disabled by default. |
| `time_up`, `last_five_minutes` | binary_sensor | From `group`. |
| `tv_reachable` | binary_sensor | Connectivity device class, diagnostic. |
| `stop_now`, `add_15_minutes`, `add_30_minutes`, `unlimited_today`, `block_today`, `clear_overrides` | button | Everyone. Only when `coordinator.control` is on, with `entity_registry_visible_default=False`. |

**Each kid's device** (`TellyboxProfileEntity`, added through `add_profile_entities`):

| Key | Platform | Value and notes |
|---|---|---|
| `time_left` | sensor | `remaining_s`, duration; None when unlimited. |
| `time_used_today` | sensor | `used_s`, duration, `state_class` total_increasing (it resets daily). |
| `allowance_today` | sensor | `allowance_s + extra_s`. Diagnostic. |
| `session_time` | sensor | `session_elapsed_s`. |
| `watching`, `time_up`, `last_five_minutes`, `blocked`, `unlimited` | binary_sensor | From the profile. |
| `add_15_minutes`, `add_30_minutes`, `unlimited_today`, `block_today`, `clear_overrides` | button | This kid only (`profile_ids=[id]`). Only with control, hidden by default. |

- **Actions:** buttons and player commands go through `coordinator.async_command`.
- **Tests:**
  - the entity states from the fixture (Mila watching, Noah out of time);
  - updates from a pushed state;
  - a new kid appearing adds entities;
  - buttons make the right client calls, with `profile_ids`;
  - no buttons with control off;
  - the player's state, browse and play (including the time-up error);
  - the units, device classes and the disabled or hidden defaults;
  - the unique ids and device layout.

## Execution

- **Subagents:** A, B and C run in parallel on Sonnet, each in its own git worktree off the contract commit of its repository.
  - B and C both work in `ha-tellybox`: B owns `__init__.py`, `coordinator.py`, `config_flow.py`, `services.yaml` and `diagnostics.py`; C owns the four platform files.
  - Neither changes `entity.py`, `const.py`, `strings.json` or `conftest.py` without reporting it. They may add keys to `strings.json` if they must, but not rename them.
- **The controller:**
  - merges and reviews;
  - writes the nl and de translations;
  - runs an end-to-end check: pytellybox's mock server, and read-only calls against the owner's Tellybox;
  - tags v0.1.0 of both repositories.
- **Checks:**
  - `pytest` in both repositories;
  - `hassfest` and the HACS validation in CI.

## Owner checks (on the real Home Assistant)

1. On pypi.org, add a pending trusted publisher: project `pytellybox`, owner `sandermvanvliet`, repository `pytellybox`, workflow `publish.yml`, environment `pypi`. Then the `v0.1.0` tag publishes the package.
2. In HACS: Custom repositories, add `sandermvanvliet/ha-tellybox` (Integration), install it, and restart Home Assistant.
3. Create a "Home Assistant" token (read and control) on Tellybox's Integrations page, then add the integration with the Tellybox URL and that token.
4. A Tellybox device with one device per kid appears, and the time left matches the dashboard.
5. Pressing a kid's "Add 15 minutes" moves the sun on that kid's phone, and Tellybox's history shows "via Home Assistant".
6. Play an episode from the media player and see it on the TV. With a kid out of time, it is refused with a message.
7. Revoke the token in Tellybox: Home Assistant asks for a new one (reauth).
