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
  - the subscription inbox: uploads pending, subscriptions failing, and when the latest upload arrived (a timestamp, to trigger an automation on every new upload);
  - active sessions (the TV and in-app playback, listed in the attributes);
  - why time is up (allowance, session maximum or blocked) and what playback does next (continue, finish then stop, stop now);
  - the next daily reset (diagnostic);
  - media disk use (diagnostic, disabled by default).
- **Binary sensors:** time up, last five minutes, TV reachable.
- **Buttons for everyone:** stop now, add 15 or 30 minutes, unlimited today, block today, clear today's overrides.

**A device for each kid**, added and removed as profiles change in Tellybox, with:
- **Sensors:**
  - time left;
  - time used today (usable in long-term statistics);
  - allowance today (with extra time, diagnostic);
  - session time;
  - maximum session, and where the allowance and the maximum session come from (default, custom or unlimited; diagnostic);
  - visible shows (how many shows the kid can see);
  - watching on (the TV's name, or the browser the kid watches on).
- **Binary sensors:** watching, time up, last five minutes, blocked today, unlimited today, and *no visible shows* (a problem sensor for a kid whose app is empty).
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

## Events and automations

The integration fires a Home Assistant bus event called `tellybox_event` for each state transition. Use it in automations to react to Tellybox events without writing template triggers on binary sensors.

All events carry these payload keys:

| Key | Value |
|---|---|
| `type` | The event type (see table below). |
| `device_id` | Home Assistant device registry id of the device the event is about (a kid's device, or the Tellybox device). |
| `instance_id` | The Tellybox server's instance id. |
| `profile_id` | *(kid events only)* The kid's profile id. |
| `profile_name` | *(kid events only)* The kid's name. |

**Event types:**

| Type | Device | Fires when | Extra keys |
|---|---|---|---|
| `time_up` | kid | The kid may not pick again. | `reason` (`allowance`, `session_max`, `blocked`, or `None`) |
| `last_five_minutes` | kid | Last five minutes of the allowance or session start. | |
| `started_watching` | kid | The kid started playback. | |
| `stopped_watching` | kid | Playback stopped. | |
| `override_applied` | kid | An override was applied. | `override` (`extra_time`, `unlimited`, `blocked`, or `cleared`); `minutes` (for `extra_time` only) |
| `inbox_item_arrived` | Tellybox | A new subscription upload arrived. | `pending` (int, number of uploads awaiting review) |
| `tv_unreachable` | Tellybox | The TV went offline. | |
| `tv_reachable` | Tellybox | The TV came back online. | |

### Device triggers

In the Home Assistant automation editor, each device offers its event types as device triggers. Choose **Device → Tellybox → *[event type]*** to trigger on that event.

### YAML example

Send a notification to a parent's phone when Mila stops watching:

```yaml
triggers:
  - trigger: event
    event_type: tellybox_event
    event_data:
      type: stopped_watching
      profile_name: Mila
actions:
  - action: notify.notify
    data:
      message: "Mila stopped watching."
```

### Limits

- **No events on Home Assistant startup:** the first state yields no events, so a restart mid-playback doesn't fire a burst. A change that happens while the connection to Tellybox is down is reported once, when it comes back.
- **No override attribution:** `override_applied` cannot say who applied it (an admin page, Home Assistant or another token): Tellybox's state doesn't carry that.
- **No stop-now event:** Tellybox's state doesn't record a *stop now*, so it has no event of its own. Playback ending shows up as `stopped_watching`.
- **`time_up` ≠ "TV off":** `time_up` fires when the kid *may not pick again*. The episode in progress usually runs on through the finish-the-episode grace period (up to 15 minutes), and `stopped_watching` fires when playback really ends. **Automations that turn the TV off should wait for `stopped_watching`, not act on `time_up` alone.** (Block and stop-now stop at once; those are actions, not events.)

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

## Repairs

Home Assistant shows problems in *Settings → Repairs* when:
- **The TV is unreachable** for longer than the warning threshold (default: 60 minutes). Appears once Tellybox can't reach its Chromecast for that duration. Check that the Chromecast is powered and on the network; it clears by itself when the TV is back online.
- **A kid has no visible shows** (default: after 24 hours with zero shows). The kid app is empty until at least one show is assigned in Tellybox's admin pages.
- **Subscriptions are failing** (7 days or longer). Channel subscriptions in the inbox stopped working; check them in Tellybox's admin pages. This appears as a Repairs entry in Home Assistant (it is not a notification Tellybox sends).
- **The media disk is low on space** (default: below 5 GB free). Free up space or add storage in Tellybox.

The TV and disk limits are options in the integration's configuration: **Minutes before a TV warning** (0 turns the TV warning off) and **Free disk space warning (GB)** (0 turns the disk warning off). All issues clear by themselves when the condition improves. **None of these can be fixed from Home Assistant** — they all need an action in Tellybox's admin pages.

The checks pause when the connection to Tellybox is down (entities show unavailable) and resume when it returns.

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
