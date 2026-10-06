# Events and device triggers

The Tellybox integration fires Home Assistant events and offers device triggers for automations. This page lists them. Back to the [README](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md).

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
