# Tellybox for Home Assistant

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

**A Tellybox device**, with:
- **Media player:**
  - what's playing, with its thumbnail;
  - pause and resume;
  - browse continue watching and the shows, and play an episode (for the kids who watched last);
  - stop, with parent controls on.
- **Sensors:**
  - now playing (show and episode);
  - time left for the kids watching;
  - downloads awaiting approval;
  - the download queue;
  - media disk use (diagnostic, disabled by default).
- **Binary sensors:** time up, last five minutes, TV reachable.
- **Buttons for everyone:** stop now, add 15 or 30 minutes, unlimited today, block today, clear today's overrides.

**A device for each kid**, added and removed as profiles change in Tellybox, with:
- **Sensors:**
  - time left;
  - time used today (usable in long-term statistics);
  - allowance today (with extra time, diagnostic);
  - session time.
- **Binary sensors:** watching, time up, last five minutes, blocked today, unlimited today.
- **Buttons for that kid:** add 15 or 30 minutes, unlimited today, block today, clear today's overrides.

The override buttons are hidden from auto-generated dashboards. Put them on a parent dashboard on purpose (see *Safety*).

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

## Example automations

Speak a warning at five minutes left:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.tellybox_last_five_minutes
    to: "on"
actions:
  - action: tts.speak
    target: { entity_id: tts.home_assistant_cloud }
    data:
      media_player_entity_id: media_player.kitchen_speaker
      message: "Five more minutes of TV."
```

Turn the TV off two minutes after time is up, once playback has stopped:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.tellybox_time_up
    to: "on"
    for: "00:02:00"
conditions:
  - condition: state
    entity_id: media_player.tellybox
    state: idle
actions:
  - action: media_player.turn_off
    target: { entity_id: media_player.living_room_tv }
```

Block watching at 18:30 on school nights:

```yaml
triggers:
  - trigger: time
    at: "18:30:00"
conditions:
  - condition: time
    weekday: [sun, mon, tue, wed, thu]
actions:
  - action: tellybox.block_today
    target: { device_id: YOUR_TELLYBOX_DEVICE_ID }
```

Get a notification when downloads wait for approval:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.tellybox_downloads_awaiting_approval
    above: 0
actions:
  - action: notify.mobile_app_parent_phone
    data:
      message: "{{ states('sensor.tellybox_downloads_awaiting_approval') }} downloads wait for approval in Tellybox."
```

## Safety

- **Hide Home Assistant's own Cast media player** for the Chromecast from dashboards that kids can reach. Tellybox only times and controls playback it started, so casting from Home Assistant directly isn't counted.
- **Put the override buttons on a parent-only dashboard.** Home Assistant has no per-entity permissions for non-admin users.
- **Give each integration its own token,** and use a read-only token for displays.
- **Keep Tellybox on your LAN or Tailscale,** preferably behind HTTPS. Tokens travel only to your own Tellybox.

## Development

```sh
python3.14 -m venv .venv && .venv/bin/pip install -r requirements_test.txt pytellybox
.venv/bin/python -m pytest -q
```

The tests use a fake client, plus [`pytellybox`](https://github.com/sandermvanvliet/pytellybox)'s mock Tellybox for an end-to-end run. The plan and progress log are in `docs/`.

Licensed under Apache-2.0.
