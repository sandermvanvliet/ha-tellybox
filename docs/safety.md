# Safety

## A dashboard is not a security boundary

Home Assistant has no per-entity permissions, and a non-admin user can still call services. Hiding the override buttons from a dashboard does not stop anyone who can open Home Assistant from pressing them, or from calling `tellybox.add_time` directly. Treat the dashboard as convenience and add the protections below.

## Layered protection

- **Parent dashboard in YAML mode with `require_admin: true`.** Only admin users see it. See the [dashboard examples](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards.md).
- **A separate non-admin Home Assistant user for the kid tablet,** showing only the read-only kid-safe view ([kid-safe.yaml](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/dashboards/kid-safe.yaml)). It has no buttons and no media controls.
- **A read-only token, with Parent controls off,** for any Home Assistant a kid can reach. Create the token in Tellybox with *Read only* and turn off **Parent controls** in the integration's options. With Parent controls off the buttons are not created and the override actions are refused.
- **One token per integration.** Revoking it in Tellybox stops that Home Assistant at once, and Home Assistant asks for a new one.
- **Hide Home Assistant's own Cast media player** for the Chromecast from anything a kid can reach. Tellybox only times and controls playback it started, so other casts are untimed.
- **Keep Tellybox on your LAN or Tailscale,** preferably behind HTTPS. Tokens travel only to your own Tellybox.

## The real enforcement is Tellybox's timer

The integration never becomes a way around the timer. Playing from Home Assistant uses the kid API, and Tellybox refuses it when a kid is out of time. Every override goes through the Tellybox admin API, so who can press an override button is the question the layers above answer.

## Entity visibility defaults

- The override buttons (all of them, for the Tellybox device and for each kid) are hidden from auto-generated dashboards, and exist only with Parent controls on.
- Media disk use is disabled by default.
- Diagnostic entities (such as the next daily reset, TV reachable and the allowance details) are hidden from auto-generated dashboards.

The [entity reference](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/entities.md) lists each entity's defaults.

## Phone notifications

Anyone holding the parent's phone can tap the add-time button in the [add-time notification blueprint](https://github.com/sandermvanvliet/ha-tellybox/blob/main/README.md#blueprints). It carries the same trust as the override buttons.

## Repairs are not notifications

The entries in *Settings → Repairs* are Home Assistant entries. Tellybox does not send them as notifications. See [Repairs](https://github.com/sandermvanvliet/ha-tellybox/blob/main/docs/repairs.md).
