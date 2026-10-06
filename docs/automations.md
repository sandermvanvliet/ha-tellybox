# Automations

These are copy-paste automations using Tellybox entities and actions. For some common automations, ready-made, configurable versions exist as [blueprints](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md#blueprints).

## Block at 18:30 on school nights

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

## Notify when downloads await approval

Downloads awaiting approval are held playlist downloads; for new subscription uploads use the [Inbox ping blueprint](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md#blueprints).

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

## Notify when a new inbox upload arrives

```yaml
triggers:
  - trigger: state
    entity_id: sensor.tellybox_latest_inbox_upload
    not_from:
      - unavailable
      - unknown
    not_to:
      - unavailable
      - unknown
actions:
  - action: notify.mobile_app_parent_phone
    data:
      message: "Tellybox upload: {{ states('sensor.tellybox_inbox_pending') }} pending approval."
```

## Notify when subscriptions are failing

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.tellybox_subscriptions_failing
    above: 0
actions:
  - action: notify.mobile_app_parent_phone
    data:
      message: "{{ states('sensor.tellybox_subscriptions_failing') }} subscriptions failing. Check Tellybox admin."
```

## Alert when a kid has no visible shows

A new kid starts with no shows by design; this alerts you after the app has been empty for a while.

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.mila_no_visible_shows
    to: "on"
    for:
      hours: 24
actions:
  - action: notify.mobile_app_parent_phone
    data:
      message: "Mila's Tellybox app has no shows. Assign shows in Tellybox admin."
```

## Speak when a kid's time is up

Time up does not mean playback stopped. The episode in progress usually runs on through the finish-the-episode grace period (up to 15 minutes), and playback ends after that or when the kid leaves the app.

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.mila_time_up
    to: "on"
actions:
  - action: tts.speak
    target: { entity_id: tts.home_assistant_cloud }
    data:
      media_player_entity_id: media_player.kitchen_speaker
      message: "Mila is out of time."
```

### Turn off the TV only after playback stops

Playback may continue up to 15 minutes after time-up (finish-the-episode grace); the TV turns off only once the Tellybox player is idle. If the player is still playing after the wait, nothing is turned off. The [TV off at time up blueprint](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md#blueprints) does the same with settings.

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.tellybox_time_up
    to: "on"
actions:
  - wait_template: "{{ states('media_player.tellybox') in ['idle', 'off'] }}"
    timeout:
      minutes: 30
    continue_on_timeout: false
  - condition: state
    entity_id: binary_sensor.tellybox_time_up
    state: "on"
  - action: media_player.turn_off
    target: { entity_id: media_player.living_room_tv }
```

## Reminder before the daily reset

The *Next daily reset* sensor's state is a timestamp. This runs once, when the reset comes within an hour.

```yaml
triggers:
  - trigger: template
    value_template: >-
      {{ 0 < as_timestamp(states('sensor.tellybox_next_daily_reset'), 0) - as_timestamp(now()) <= 3600 }}
actions:
  - action: notify.mobile_app_parent_phone
    data:
      message: "Tellybox resets within the hour. Today's extra time, unlimited and blocks will clear."
```
