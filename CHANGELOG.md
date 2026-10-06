# Changelog

Release notes for the Tellybox integration. The workflow in `.github/workflows/release.yml` publishes the section for a version as that release's notes (see `docs/RELEASING.md`).

## Unreleased

- Home Assistant events and device triggers for Tellybox: receive bus events (`tellybox_event`) and use device triggers for time up, last five minutes, started/stopped watching, override applied, inbox item arrived, TV reachable/unreachable.
- Diagnostics now redact the browser device ids, labels and keys of in-app sessions.
- A sensor for every browser playing in the kid app ("Watching on <browser>"), and `target` and `state` attributes on each kid's "Watching on" sensor.
- Repairs: Home Assistant now warns when Tellybox can't reach the TV for a while, when a kid has no shows to watch, when subscriptions keep failing, and when the media disk is low on space. Thresholds for the TV and the disk are in the integration's options.

## 0.3.0

- New sensors on the Tellybox device: inbox pending, subscriptions failing, latest inbox upload, active sessions, time up reason, playback action and next daily reset.
- New on each kid's device: visible shows, maximum session, allowance source, maximum session source and watching on, plus a *no visible shows* problem sensor.
- A kid with an unlimited allowance no longer breaks the state or shows a wrong "allowance today".
- Requires pytellybox 0.2.0.

## 0.1.1

- Branding: the HACS and Home Assistant icon and logo now use Tellybox's mark and logo (light and dark); README logo header; social preview.

## 0.1.0

- First release: a Tellybox device and a device per kid, time-limit and bonus-time controls, a media player to play from the library, and reauthentication when the token is revoked.
