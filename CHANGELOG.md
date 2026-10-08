# Changelog

Release notes for the Tellybox integration. The workflow in `.github/workflows/release.yml` publishes the section for a version as that release's notes (see `docs/RELEASING.md`).

## Unreleased

## 0.6.0

- Events now use Tellybox's typed events when it has them: `stopped_watching` says why playback ended, `override_applied` says who applied the override, and there is a new `download_ready` event and device trigger. Older Tellybox versions keep working: the integration derives events from state changes as before (needs pytellybox 0.6.0 and, for typed events, Tellybox 0.6.0).
- Requires pytellybox 0.6.0 (installed automatically). Typed events need Tellybox 0.6.0; against an older Tellybox the integration derives events from state changes as before. Everything else works as in 0.5.0.

## 0.5.0

- Per-kid sensors for the time used yesterday, the 7-day average and the last watched episode (needs a Tellybox with the history endpoint, HA-12; older Tellybox gets no history sensors).
- Requires pytellybox 0.5.0 (installed automatically). The history sensors need Tellybox 0.5.0; against an older Tellybox they simply don't appear. Everything else works as in 0.4.0.

## 0.4.0

- Each kid's device has a Picture entity with the kid's photo or avatar (needs a Tellybox with the profile fields, HA-11).
- Per-kid sensors for whether a kid may watch in the app and for the kid app style (needs a Tellybox with the profile fields, HA-11; older Tellybox shows them as unknown).
- Documentation: dashboard examples for parents and a read-only kid view, an automations page, a generated entity reference, and a safety page; the README is now a shorter landing page.
- Blueprints to import: five-minute warning, TV off at time up, an actionable 'add time' phone notification, inbox ping and an empty-kid-app alert (English only).
- Each kid's device has a media player: it shows what that kid is watching and plays an episode for that kid only. It has no pause or stop, because Tellybox's are household-wide. Tellybox still refuses when the kid is out of time.
- Home Assistant events and device triggers for Tellybox: receive bus events (`tellybox_event`) and use device triggers for time up, last five minutes, started/stopped watching, override applied, inbox item arrived, TV reachable/unreachable.
- Diagnostics now redact the browser device ids, labels and keys of in-app sessions.
- A sensor for every browser playing in the kid app ("Watching on <browser>"), and `target` and `state` attributes on each kid's "Watching on" sensor.
- Repairs: Home Assistant now warns when Tellybox can't reach the TV for a while, when a kid has no shows to watch, when subscriptions keep failing, and when the media disk is low on space. Thresholds for the TV and the disk are in the integration's options.
- Requires pytellybox 0.4.0 (installed automatically). The Picture entity's photo and the two new per-kid sensors need Tellybox 0.4.0; against an older Tellybox the sensors show unknown and the picture falls back to the kid's avatar. Everything else works with Tellybox 0.3.0.

## 0.3.0

- New sensors on the Tellybox device: inbox pending, subscriptions failing, latest inbox upload, active sessions, time up reason, playback action and next daily reset.
- New on each kid's device: visible shows, maximum session, allowance source, maximum session source and watching on, plus a *no visible shows* problem sensor.
- A kid with an unlimited allowance no longer breaks the state or shows a wrong "allowance today".
- Requires pytellybox 0.2.0.

## 0.1.1

- Branding: the HACS and Home Assistant icon and logo now use Tellybox's mark and logo (light and dark); README logo header; social preview.

## 0.1.0

- First release: a Tellybox device and a device per kid, time-limit and bonus-time controls, a media player to play from the library, and reauthentication when the token is revoked.
