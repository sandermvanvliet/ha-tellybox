# Progress

Running log for the Home Assistant integration. The plan is `docs/plan.md`; Tellybox's own log is its `docs/PROGRESS.md`.

## Phase 1 (v0.1.0), done
- 2026-09-29: plan approved by the owner (two Apache-2.0 repositories, PyPI plus HACS, a device per kid, HA 2026.4 or later).
- Contract committed in both repositories: pytellybox models, errors, client signatures and CI with the PyPI publish; the integration's manifest, constants, entity base, coordinator contract, all strings and the fake client.
- Built by three Sonnet subagents from the contract, then merged and reviewed by the controller (2026-09-29).
  - **pytellybox (A):**
    - the client (error mapping, token kept out of messages, SSE parser);
    - `MockTellybox` and `python -m pytellybox.mock`;
    - 69 tests.
  - **Core (B):**
    - the coordinator: event stream, backoff from 1 s to 60 s, unavailable after 60 s, reauth on 401, and commands with translated errors;
    - setup and unload;
    - removing deleted kids' devices;
    - the config flow (user, reauth, options);
    - six actions with device targeting;
    - diagnostics with redaction.
  - **Entities (C):** the media player (browse and play through the kid API), sensors, binary sensors and buttons, with the Tellybox device plus one device per kid.
- **Controller:**
  - switched the platform tests to the real setup (they hung on a real client);
  - removed the null-name test workaround;
  - fixed `runtime_data` access on unloaded entries in the action handler;
  - nl and de translations, with a completeness test;
  - an end-to-end test (the real client against the mock over HTTP: a button press moves the kid's time left);
  - the README;
  - a brand icon for HACS;
  - hassfest fixes (no null names, no URLs in strings).
- 101 tests. CI: hassfest, HACS validation and the tests.
- Released v0.1.0 on both repositories (2026-09-29). pytellybox 0.1.0 is on PyPI (trusted publishing set up by the owner).
- Installed on the owner's Home Assistant through HACS, and the integration is set up (2026-09-29).
- **Owner checks passed (2026-09-29):**
  - the Tellybox device and both kid devices appear;
  - +15 from Home Assistant moves the sun, and history says "via Home Assistant";
  - play from the media player works, and is refused when time is up;
  - revoking the token starts reauth.

## 0.1.1 (2026-09-29)
- Branding: the HACS and Home Assistant icon and logo now use Tellybox's mark and logo (light and dark); README logo header; social preview.

## API coverage (2026-10-05, in review)
- pytellybox: the whole admin API and the kid state (sessions, inbox, allowance and session sources, visible shows, kid events), and a fix for an unlimited (null) allowance. The in-app player endpoints are left out on purpose (HA-8).
- Integration: sensors for the inbox (HA-9), visible shows (HA-10), sessions, time-up reason, playback action, next reset and the sources, plus a *no visible shows* problem sensor. Needs pytellybox 0.2.0, so it can't merge before that release.

## Next
Phase 2 of the Home Assistant plan, when the owner wants it:
- typed events on Tellybox's admin stream (F4), with HA bus events and device triggers;
- opt-in zeroconf discovery;
- blueprints (five-minute warning, TV off at time-up, an actionable "add time" notification).
