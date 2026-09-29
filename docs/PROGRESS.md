# Progress

Running log for the Home Assistant integration. The plan is `docs/plan.md`; Tellybox's own log is its `docs/PROGRESS.md`.

## Phase 1 (v0.1.0), in progress
- 2026-09-29: plan approved by the owner (two Apache-2.0 repositories, PyPI plus HACS, a device per kid, HA 2026.4 or later).
- Contract committed in both repositories: pytellybox models, errors, client signatures and CI with the PyPI publish; the integration's manifest, constants, entity base, coordinator contract, all strings and the fake client.
- **Next:** three subagents in parallel: pytellybox (A), setup/coordinator/actions (B), entities (C).
