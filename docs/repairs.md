# Repairs

The Tellybox integration raises Home Assistant Repairs entries for problems that need attention. This page lists them. Back to the [README](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md).

Home Assistant shows problems in *Settings → Repairs* when:
- **The TV is unreachable** for longer than the warning threshold (default: 60 minutes). Appears once Tellybox can't reach its Chromecast for that duration. Check that the Chromecast is powered and on the network; it clears by itself when the TV is back online.
- **A kid has no visible shows** (default: after 24 hours with zero shows). The kid app is empty until at least one show is assigned in Tellybox's admin pages.
- **Subscriptions are failing** (7 days or longer). Channel subscriptions in the inbox stopped working; check them in Tellybox's admin pages. This appears as a Repairs entry in Home Assistant (it is not a notification Tellybox sends).
- **The media disk is low on space** (default: below 5 GB free). Free up space or add storage in Tellybox.

The TV and disk limits are options in the integration's configuration: **Minutes before a TV warning** (0 turns the TV warning off) and **Free disk space warning (GB)** (0 turns the disk warning off). All issues clear by themselves when the condition improves. **None of these can be fixed from Home Assistant** — they all need an action in Tellybox's admin pages.

The checks pause when the connection to Tellybox is down (entities show unavailable) and resume when it returns.
