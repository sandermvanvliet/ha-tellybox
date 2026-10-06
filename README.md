<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/sandermvanvliet/Tellybox/main/docs/images/brand/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/sandermvanvliet/Tellybox/main/docs/images/brand/logo.svg" alt="Tellybox" width="420">
  </picture>
  <br>for Home Assistant
</h1>

A Home Assistant integration for [Tellybox](https://github.com/sandermvanvliet/Tellybox), the self-hosted app that lets young kids pick parent-approved videos for the TV within a daily time allowance.

With it you can:
- see what's on the TV and how much time each kid has left, on any dashboard;
- give extra time, unlimited today or a block, from dashboards, automations and phone notifications;
- automate around the timer: a spoken "five more minutes", the TV off when time is up, bedtime blocks, chores that earn minutes.

It never becomes a way around the timer. Everything goes through Tellybox, and playing from Home Assistant is refused when someone is out of time.

## Requirements

- Tellybox with the admin API (version 2026.09.29 or later).
- Home Assistant 2026.4 or later.

## Install

1. **Install through HACS.** In HACS → ⋮ → *Custom repositories*, add `https://github.com/sandermvanvliet/ha-tellybox` with type *Integration*. Install **Tellybox**, then restart Home Assistant.
2. **Create a token.** In Tellybox, open *Admin → Integrations* and create a token.
   - Choose **Read and control** for parent controls, or **Read only** for a status display.
   - Copy the token; it's shown only once.
3. **Add the integration.** In Home Assistant: *Settings → Devices & services → Add integration → Tellybox*. Enter the address you open Tellybox on and the token.

Revoking the token in Tellybox stops Home Assistant at once, and Home Assistant asks for a new one.

With a read-only token, turn off **Parent controls** in the integration's options.

## What you get

The full list, generated from the code, is in the [entity reference](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/entities.md). In short:

**A Tellybox device**, with:
- **Media player:** what's playing with its thumbnail, pause and resume, browsing continue watching and the shows, playing an episode (for the kids who watched last), and stop with parent controls on.
- **Sensors:** now playing, time left, downloads awaiting approval, the download queue, the subscription inbox (uploads pending, subscriptions failing, when the latest upload arrived), active sessions, why time is up and what playback does next, the next daily reset and media disk use (diagnostic; disk use is disabled by default).
- **Watching on <browser> sensors:** one sensor per browser playing in the kid app, created when playback starts and removed 30 seconds after it ends. The state is loading, playing, paused or buffering. Attributes: the browser label, episode title and position, the kids and their profile ids, and the episode id and show id. Title and position are not recorded in history. These sensors are created dynamically, so they are not in the entity reference.
- **Binary sensors:** time up, last five minutes, TV reachable.
- **Buttons (parent controls):** stop now, add 15 or 30 minutes, unlimited today, block today, clear today's overrides.

**A device for each kid**, added and removed as profiles change in Tellybox, with:
- **Media player:** shows what *that kid* is watching and plays an episode *for that kid only*. Browsing shows only what that kid can see. Playing always starts on the TV, never in the kid's browser, and Tellybox refuses it when the kid is out of time. There is no pause, play or stop: Tellybox's are household-wide, so use the Tellybox device's player for those. Playing for one kid replaces any group playback that kid is in (Tellybox's rule, the same call the kid's own app makes). While the kid watches in a browser it is a read-only view, with a `watching_on` attribute holding the browser label.
- **Sensors:** time left, time used today, allowance today, session time, maximum session and where the allowance and maximum come from, visible shows, and watching on (the TV's name or the browser, with `target` and `state` attributes).
- **Binary sensors:** watching, time up, last five minutes, blocked today, unlimited today, and no visible shows.
- **Buttons (parent controls):** add 15 or 30 minutes, unlimited today, block today, clear today's overrides.

The override buttons are hidden from auto-generated dashboards. Put them on a parent dashboard on purpose (see [Safety](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/safety.md)).

## Actions

Each action targets devices: the **Tellybox device** means everyone, and **kids' devices** mean those kids.

| Action | Fields |
|---|---|
| `tellybox.add_time` | `minutes` (1–240) |
| `tellybox.set_unlimited_today` | |
| `tellybox.block_today` | |
| `tellybox.clear_overrides` | Clears unlimited and block; extra minutes stay. |
| `tellybox.stop_now` | |
| `tellybox.play_episode` | `episode_id`. Plays for the kids' devices, or the kids who watched last. It is refused when one of them is out of time. |

## Blueprints

Five ready-to-import automation blueprints cover common parent automations, so you don't hand-write YAML. Blueprints are English only (Home Assistant has no translation mechanism for blueprint text). HACS does not install them: import by URL from the *My Home Assistant* badge below, or in *Settings → Automations → Blueprints → Import*.

| Blueprint | Entities | Import |
|---|---|---|
| **Five-minute warning** — speak, flash a light, or send a notification when the kids have five minutes left. | Tellybox or kid `last_five_minutes` binary sensor | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsandermvanvliet%2Fha-tellybox%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftellybox%2Ffive_minute_warning.yaml) |
| **TV off at time-up** — turn off the TV after the kids' allowance ends and playback has stopped. *Playback may continue up to 15 minutes after time-up (finish-the-episode grace); the TV turns off only once the player is idle.* | Tellybox `time_up` binary sensor (typically the Tellybox device's), Tellybox media player, and the TV to control | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsandermvanvliet%2Fha-tellybox%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftellybox%2Ftv_off_at_time_up.yaml) |
| **Add time notification** — send an actionable phone notification at time-up or five minutes left; tapping adds time. Requires the Home Assistant mobile app. *Anyone holding the parent's phone can tap the button; it carries the same trust as the override buttons.* | Kid's `time_up` or `last_five_minutes` binary sensor (not the Tellybox device's), mobile app device | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsandermvanvliet%2Fha-tellybox%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftellybox%2Fadd_time_notification.yaml) |
| **Inbox ping** — notify when a subscription upload waits for approval. | Inbox `latest_received_at` and `pending` sensors, mobile app device | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsandermvanvliet%2Fha-tellybox%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftellybox%2Finbox_ping.yaml) |
| **Empty kid app alert** — alert when a kid has no visible shows to watch. | Kid `no_visible_shows` binary sensor, mobile app device | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsandermvanvliet%2Fha-tellybox%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftellybox%2Fempty_kid_app_alert.yaml) |

## Events and automations

The integration fires a `tellybox_event` bus event for each state transition and offers device triggers in the automation editor. See [Events and device triggers](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/events.md) for the event types, payload, YAML example and limits.

## Example automations

Copy-paste automations (block on school nights, notifications for downloads and the inbox, and more) are in [Automations](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/automations.md). For a spoken warning, an add-time notification or the TV off at time-up, use the [Blueprints](#blueprints).

## Repairs

Home Assistant shows problems in *Settings → Repairs* when the TV is unreachable, a kid has no visible shows, subscriptions keep failing or the media disk is low on space. See [Repairs](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/repairs.md).

## Documentation

- [Dashboards](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards.md): a parent dashboard ([admin.yaml](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards/admin.yaml)) and a read-only kid view ([kid-safe.yaml](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards/kid-safe.yaml)).
- [Automations](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/automations.md): copy-paste YAML automations.
- [Events and device triggers](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/events.md)
- [Repairs](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/repairs.md)
- [Entity reference](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/entities.md): every entity, generated from the code.
- [Safety](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/safety.md): what a dashboard can and cannot protect.

## Safety

- A dashboard is not a security boundary. Put the override buttons on a parent-only dashboard and read [Safety](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/safety.md) for the layered protection.
- **Hide Home Assistant's own Cast media player** for the Chromecast from dashboards that kids can reach. Tellybox only times and controls playback it started, so casting from Home Assistant directly isn't counted.
- Give each integration its own token, use a read-only token for displays, and keep Tellybox on your LAN or Tailscale, preferably behind HTTPS.

## Development

```sh
python3.14 -m venv .venv && .venv/bin/pip install -r requirements_test.txt pytellybox
.venv/bin/python -m pytest -q
```

The tests use a fake client, plus [`pytellybox`](https://github.com/sandermvanvliet/pytellybox)'s mock Tellybox for an end-to-end run. The plan and progress log are in `docs/`.

Licensed under Apache-2.0.
