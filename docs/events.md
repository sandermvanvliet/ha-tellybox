# Events and device triggers

The Tellybox integration fires Home Assistant events and offers device triggers for automations. This page lists them. Back to the [README](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md).

The integration fires a Home Assistant bus event called `tellybox_event` for each state transition (and, with a recent Tellybox, for each typed event it sends). Use it in automations to react to Tellybox events without writing template triggers on binary sensors.

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
| `last_five_minutes` | kid | Last five minutes of the allowance or session start. | `remaining_s` *(typed events only)* |
| `started_watching` | kid | The kid started playback. | *(typed events only)* `episode_id`, `show_id`, `title`, `show`, `target` (`tv` or `device`), `label` (the TV's name or the browser label) |
| `stopped_watching` | kid | Playback stopped. | *(typed events only)* `reason`, `position_s`, plus the same keys as `started_watching` |
| `override_applied` | kid | An override was applied. | `override` (`extra_time`, `unlimited`, `blocked`, or `cleared`); `minutes` (for `extra_time` only); *(typed events only)* `source` (the token's name, or `None` for the admin pages). With typed events `override` can also be `stop_now`. |
| `inbox_item_arrived` | Tellybox | A new subscription upload arrived. | `pending` (int, number of uploads awaiting review); *(typed events only)* `new_items` |
| `download_ready` | Tellybox | A held download is waiting for approval. Typed events only. | `held_ready`, `new_ready` |
| `tv_unreachable` | Tellybox | The TV went offline. | |
| `tv_reachable` | Tellybox | The TV came back online. | |

### Where events come from

- **Typed events (a recent Tellybox):** when Tellybox lists the `typed_events` capability, it sends the events itself and the integration passes them on. These carry what a state change can't tell: `stopped_watching` has a `reason` (`finished`, `replaced`, `stopped`, `parent_stop`, `time_up`, `blocked`, `taken_over`, `disconnected`, `restart` or `load_failed`), and `override_applied` has a `source` (the token's name, or `None` for the admin pages). The keys marked *typed events only* above are present only in this mode.
- **Derived events (an older Tellybox):** the integration compares each new state with the previous one and derives the events itself, with the keys that every event has and no more. The integration checks on every reconnect, so upgrading Tellybox takes effect without a restart of Home Assistant.
- **TV reachable and unreachable** are always derived by the integration; Tellybox has no typed event for them.
- **Events during an outage are lost.** Typed events are not stored or replayed. An automation that must not miss *time up* should also use the time-up binary sensor, which always shows the current state.

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
- **No override attribution without typed events:** with a Tellybox that has no typed events, `override_applied` cannot say who applied it (an admin page, Home Assistant or another token): its state doesn't carry that. With typed events it has `source`.
- **No stop-now event without typed events:** an older Tellybox's state doesn't record a *stop now*, so it has no event of its own and playback ending shows up as `stopped_watching`. With typed events, a stop now gives `override_applied` with `override` `stop_now`.
- **`time_up` ≠ "TV off":** `time_up` fires when the kid *may not pick again*. The episode in progress usually runs on through the finish-the-episode grace period (up to 15 minutes), and `stopped_watching` fires when playback really ends. **Automations that turn the TV off should wait for `stopped_watching`, not act on `time_up` alone.** (Block and stop-now stop at once; those are actions, not events.)
