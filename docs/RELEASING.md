# Releasing

How a release of the Tellybox integration is made. It mirrors [Tellybox's own process](https://github.com/sandermvanvliet/tellybox/blob/main/docs/RELEASING.md) and the [add-on's](https://github.com/sandermvanvliet/tellybox-ha-addon/blob/main/docs/RELEASING.md): a release only happens when the owner pushes a `v*` tag. Never tag, push a tag or publish a release without the owner's explicit go-ahead.

## Versioning

[Semantic versioning](https://semver.org/): `MAJOR.MINOR.PATCH`. While the major version is 0, a minor bump may contain breaking changes and a patch bump only fixes bugs. The version lives in two places that must be equal: `version` in `pyproject.toml` and `version` in `custom_components/tellybox/manifest.json`. HACS offers an update when a new GitHub release appears.

## Before you start

- `main` is green (the *Validate* workflow passed: hassfest, HACS and tests).
- The `pytellybox` release pinned in `manifest.json` (`requirements`) is on PyPI. If this release needs a newer client, release [pytellybox](https://github.com/sandermvanvliet/pytellybox) first and bump the pin.
- `CHANGELOG.md` describes everything since the last release under `## Unreleased`, including anything a user must do when upgrading (a new minimum Tellybox or Home Assistant version, a re-setup).
- `docs/PROGRESS.md` is up to date.

## Steps

1. On a branch, set the version in `pyproject.toml` and `manifest.json` to `X.Y.Z`, and rename `## Unreleased` in `CHANGELOG.md` to `## X.Y.Z` (add a fresh empty `## Unreleased` above it). Merge by pull request.
2. Update your checkout to the merge commit on `main`.
3. Tag that commit and push the tag:

   ```sh
   git checkout main && git pull
   git tag -a vX.Y.Z -m "Tellybox integration X.Y.Z"
   git push origin vX.Y.Z
   ```

The tag must be `v` plus the exact version in both files.

## What CI does

Pushing a `v*` tag runs `.github/workflows/release.yml`, which fails before publishing anything if a check fails:

1. The tag matches the version in `pyproject.toml` and `manifest.json`.
2. `CHANGELOG.md` has a non-empty `## X.Y.Z` section.
3. The pinned `pytellybox` release exists on PyPI.
4. `pytest -q` passes.
5. The GitHub release is created (only if it doesn't exist yet), titled `X.Y.Z`, with that changelog section as its notes.

## Check the result

- The workflow run for the tag is green in the Actions tab.
- `gh release view vX.Y.Z` shows the release and the changelog notes.
- In HACS, the Tellybox integration shows the new version (HACS may need a reload of its data).

## If a release is bad

Never move or delete a tag that people may have pulled. Fix the problem on `main` and release the next patch version. Delete a release only if it was never used, for example when the workflow failed halfway, and then delete its tag too so the version can be tagged again.
