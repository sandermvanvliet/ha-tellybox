# Dashboards

Two ready-made dashboards, written as plain YAML with core Home Assistant cards only (no custom cards needed):

- [`docs/dashboards/admin.yaml`](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards/admin.yaml): the parent dashboard, with the override buttons.
- [`docs/dashboards/kid-safe.yaml`](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards/kid-safe.yaml): a read-only view for a kid's tablet.

They were written and checked against Home Assistant 2026.4. Every entity id in them is tested against the integration, and the full list is in the [entity reference](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/entities.md).

**The kid-safe view is read-only. It is not a security boundary.** It simply has no buttons, but Home Assistant has no per-entity permissions, so anyone who can open Home Assistant can still find other ways to reach the controls. Read the [safety page](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/safety.md) before you put anything on a tablet a kid can pick up. The real limit is always the timer inside Tellybox.

## Import a dashboard

### From the UI

1. Go to Settings > Dashboards > Add dashboard, choose "New dashboard from scratch", give it a title and create it.
2. Open it, choose the three-dot menu, then Edit dashboard, then the three-dot menu again and Raw configuration editor.
3. Replace everything in the editor with the contents of `admin.yaml` (or `kid-safe.yaml`), and save.

Do this once per file, so you end up with two dashboards.

### In YAML mode

Copy the files next to your `configuration.yaml` (for example into `dashboards/`) and register them. `require_admin: true` hides the parent dashboard from non-admin users in the sidebar:

```yaml
lovelace:
  dashboards:
    tellybox-parents:
      mode: yaml
      filename: dashboards/tellybox-admin.yaml
      title: Tellybox
      icon: mdi:television-play
      show_in_sidebar: true
      require_admin: true
    tellybox-telly:
      mode: yaml
      filename: dashboards/tellybox-kid-safe.yaml
      title: Telly
      icon: mdi:television
      show_in_sidebar: true
      require_admin: false
```

Restart Home Assistant (or reload the dashboards) afterwards. Hiding a dashboard from the sidebar is cosmetic: it is not a lock. See the safety page.

The buttons only exist when Parent controls is on in the integration options. With it off they show as unavailable.

## Adapt it to your kids

- The files are written for two kids, `mila` and `noah`. Replace those with your kids' names in lower case.
- Entity ids follow the device name: a kid called Mila gives `sensor.mila_time_left`. If a device was renamed, or the name has spaces or accents, the id differs. Check yours in Settings > Devices & services > Tellybox, then open a device and its entities.
- Each kid has one block of cards. For a third kid, copy a whole block and replace the name; for one kid, delete the other block. In `admin.yaml` the kid also appears in the last card (the graph), so add or remove the entity there too.
- The Tellybox device itself has ids starting `tellybox_`, for example `sensor.tellybox_time_left`.

## What the parent dashboard shows

One view, "Parents", with these cards from top to bottom:

- **Tellybox.** What is playing now (show and episode), the time left, the number of active sessions, and whether time is up or in its last five minutes. Under it are the buttons for everyone: stop now, add 15 or 30 minutes, unlimited today, block today and clear today's overrides. Stop now, unlimited and block ask for confirmation first.
- **One card per kid** (Mila, Noah). A list of time left, time used today, watching, time up, last five minutes, blocked today, unlimited today and whether the kid has no visible shows. Under it are the five buttons for that kid: add 15 minutes, add 30 minutes, unlimited today, block today and clear today's overrides. Unlimited and block ask for confirmation.
- **Inbox and downloads.** Uploads waiting in the inbox, failing subscriptions, the time of the latest inbox upload, downloads waiting for approval and the download queue.
- **Health.** Whether the TV is reachable and when the next daily reset happens.
- **Time used today.** A bar graph of each kid's time used per day for the last two weeks, from Home Assistant's long-term statistics.

Every button goes through the Tellybox admin API; none of them can start playback.

## What the kid-safe view shows

One view, "Telly". It has a "Now playing" card with the show and episode on the Tellybox, then one card per kid with time left, watching, time up and last five minutes. All tiles have their tap action set to none, so tapping does nothing. There are no buttons, no media player and no media controls.

## Custom cards (optional)

Nothing here needs custom cards. If you use HACS frontend cards such as `auto-entities` or Mushroom, you can build the per-kid blocks from a loop or style them differently. That is up to you; these files are not tested against them.

See also the [safety page](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/safety.md) and the [entity reference](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/entities.md).
