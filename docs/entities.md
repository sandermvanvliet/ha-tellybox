# Entity reference

This file is generated from the entity descriptions: do not edit it. Regenerate it with `.venv/bin/python scripts/gen_entity_docs.py`.

Entity ids follow the device name, so a renamed device or kid changes the prefix. Below, `<kid>` stands for the slug of a kid's profile name (for example `mila`).

## Tellybox device

| Entity id | Name | Category | Device class | Unit | Notes |
|---|---|---|---|---|---|
| `binary_sensor.tellybox_last_five_minutes` | Last five minutes |  |  |  |  |
| `binary_sensor.tellybox_time_up` | Time up |  |  |  |  |
| `binary_sensor.tellybox_tv_reachable` | TV reachable | diagnostic | connectivity |  |  |
| `button.tellybox_add_15_minutes` | Add 15 minutes |  |  |  | parent controls only; hidden by default |
| `button.tellybox_add_30_minutes` | Add 30 minutes |  |  |  | parent controls only; hidden by default |
| `button.tellybox_block_today` | Block today |  |  |  | parent controls only; hidden by default |
| `button.tellybox_clear_today_s_overrides` | Clear today's overrides |  |  |  | parent controls only; hidden by default |
| `button.tellybox_stop_now` | Stop now |  |  |  | parent controls only; hidden by default |
| `button.tellybox_unlimited_today` | Unlimited today |  |  |  | parent controls only; hidden by default |
| `media_player.tellybox` | (device name) |  |  |  |  |
| `sensor.tellybox_active_sessions` | Active sessions |  |  |  |  |
| `sensor.tellybox_download_queue` | Download queue |  |  |  |  |
| `sensor.tellybox_downloads_awaiting_approval` | Downloads awaiting approval |  |  |  |  |
| `sensor.tellybox_latest_inbox_upload` | Latest inbox upload |  | timestamp |  |  |
| `sensor.tellybox_inbox_pending` | Inbox pending |  |  |  |  |
| `sensor.tellybox_subscriptions_failing` | Subscriptions failing |  |  |  |  |
| `sensor.tellybox_media_disk_use` | Media disk use | diagnostic | data_size | GB | disabled by default |
| `sensor.tellybox_next_daily_reset` | Next daily reset | diagnostic | timestamp |  |  |
| `sensor.tellybox_now_playing_episode` | Now playing episode |  |  |  |  |
| `sensor.tellybox_now_playing_show` | Now playing show |  |  |  |  |
| `sensor.tellybox_playback_action` | Playback action |  | enum |  | values: continue, finish_then_stop, stop_now |
| `sensor.tellybox_time_left` | Time left |  | duration | s |  |
| `sensor.tellybox_time_up_reason` | Time up reason |  | enum |  | values: allowance, session_max, blocked |

## Each kid (`<kid>`)

| Entity id | Name | Category | Device class | Unit | Notes |
|---|---|---|---|---|---|
| `binary_sensor.<kid>_blocked_today` | Blocked today |  |  |  |  |
| `binary_sensor.<kid>_last_five_minutes` | Last five minutes |  |  |  |  |
| `binary_sensor.<kid>_no_visible_shows` | No visible shows |  | problem |  |  |
| `binary_sensor.<kid>_time_up` | Time up |  |  |  |  |
| `binary_sensor.<kid>_unlimited_today` | Unlimited today |  |  |  |  |
| `binary_sensor.<kid>_watch_in_app` | Watch in app |  |  |  |  |
| `binary_sensor.<kid>_watching` | Watching |  |  |  |  |
| `button.<kid>_add_15_minutes` | Add 15 minutes |  |  |  | parent controls only; hidden by default |
| `button.<kid>_add_30_minutes` | Add 30 minutes |  |  |  | parent controls only; hidden by default |
| `button.<kid>_block_today` | Block today |  |  |  | parent controls only; hidden by default |
| `button.<kid>_clear_today_s_overrides` | Clear today's overrides |  |  |  | parent controls only; hidden by default |
| `button.<kid>_unlimited_today` | Unlimited today |  |  |  | parent controls only; hidden by default |
| `image.<kid>_picture` | Picture |  |  |  |  |
| `media_player.<kid>` | (device name) |  |  |  |  |
| `sensor.<kid>_allowance_source` | Allowance source | diagnostic | enum |  | values: inherit, custom, unlimited |
| `sensor.<kid>_allowance_today` | Allowance today | diagnostic | duration | s |  |
| `sensor.<kid>_maximum_session` | Maximum session | diagnostic | duration | s |  |
| `sensor.<kid>_maximum_session_source` | Maximum session source | diagnostic | enum |  | values: inherit, custom, unlimited |
| `sensor.<kid>_session_time` | Session time |  | duration | s |  |
| `sensor.<kid>_time_left` | Time left |  | duration | s |  |
| `sensor.<kid>_time_used_today` | Time used today |  | duration | s |  |
| `sensor.<kid>_kid_app_style` | Kid app style | diagnostic | enum |  | disabled by default; values: icons, text |
| `sensor.<kid>_visible_shows` | Visible shows |  |  |  |  |
| `sensor.<kid>_watching_on` | Watching on |  |  |  |  |
