# Tellybox for Home Assistant

Custom Home Assistant integration (HACS, domain `tellybox`) for [Tellybox](https://github.com/sandermvanvliet/Tellybox), the self-hosted app that lets young kids pick parent-approved videos for the TV within a daily time allowance. It talks to Tellybox's admin API through the [`pytellybox`](https://github.com/sandermvanvliet/pytellybox) client, which is published to PyPI separately. The plan is in `docs/plan.md`; the running log is `docs/PROGRESS.md`.

## Hard rules

- The integration never becomes a way around the timer. Every action goes through the Tellybox admin API, and playing from Home Assistant is refused when a kid is out of time.
- Keep the integration thin: protocol and API details belong in `pytellybox`, not here. Anything needing a new API call or model means a `pytellybox` release first.
- Keep the owner's hostnames, IPs, tokens and internal domains out of committed files, tests and fixtures.

## Layout

- `custom_components/tellybox/`: the integration (config flow with reauth, coordinator, entities, services, diagnostics). `strings.json` is the source for `translations/` (English, nl, de); `tests/test_translations.py` fails when they drift.
- `tests/`: `pytest-homeassistant-custom-component`, with a scriptable fake `pytellybox` client in `tests/conftest.py`; no real Tellybox needed. `tests/test_contract.py` pins the contract with the client.
- `hacs.json` sets the minimum Home Assistant version; `manifest.json` pins the `pytellybox` release.

## How to work

- Run tests with `.venv/bin/python -m pytest -q`. CI (`.github/workflows/validate.yml`) also runs hassfest and the HACS validation.
- Add tests with every change, and add every user-facing string to `strings.json` plus all translations.
- Before coding something new, propose a short plan and wait for approval. Keep `docs/PROGRESS.md` up to date.
- Releases follow `docs/RELEASING.md`. Never tag, push a tag or publish a release without the owner's explicit go-ahead. Record user-visible changes under `## Unreleased` in `CHANGELOG.md` as you go.
- The version is in both `pyproject.toml` and `manifest.json`; only the release PR changes it.
