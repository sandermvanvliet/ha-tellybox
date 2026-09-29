# Progress

Running log for the Home Assistant integration. The plan is `docs/plan.md`; Tellybox's own log is its `docs/PROGRESS.md`.

## Phase 1 (v0.1.0), in progress
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
- **Next:** tag pytellybox v0.1.0 (needs the owner's PyPI pending publisher), release ha-tellybox v0.1.0, then the owner's checks (`docs/plan.md`).
