# Releasing Pixano

This document describes how Pixano is branched, versioned, and released. It is the reference for maintainers, and for anyone picking the project up after a quiet period.

## Principles

1. Development happens on `main`. Every pull request targets it.
2. `main` is releasable at any time. Work that is not ready for users lands behind a feature flag that defaults to off.
3. A release is a tag `vX.Y.Z` on a commit that CI has validated. Publishing the GitHub release for that tag publishes the package, the Docker image, and the documentation.
4. Release branches exist only to patch a published version. They are created from a tag and never merged back.
5. Only the latest minor version receives patch releases.

## Branches and tags

| Name                                                                           | Created from            | Purpose                                 | Lifetime                             |
| ------------------------------------------------------------------------------ | ----------------------- | --------------------------------------- | ------------------------------------ |
| `main`                                                                         |                         | The next version, always releasable     | Permanent                            |
| `feat/PIX-<n>`, `fix/PIX-<n>`, and the `docs/`, `refactor/`, `chore/` prefixes | `main`                  | One issue, one pull request into `main` | Deleted when the pull request merges |
| `release/X.Y`                                                                  | Tag `vX.Y.0`            | Patch releases `vX.Y.1`, `vX.Y.2`, ...  | Until the next minor is released     |
| Tag `vX.Y.Z`                                                                   | `main` or `release/X.Y` | A published version                     | Permanent, never moved               |

Rules:

- Release branches are named `release/X.Y`, without `v` and without a patch number. Tags are named `vX.Y.Z`. A branch is never named like a tag, because the name then becomes ambiguous for every `git` command.
- Pull requests into `main` are squash-merged: one pull request, one commit.
- A long-lived branch is never squash-merged into another. Squashing a whole release into one commit makes `git blame` and `git bisect` useless for it.
- Changes reach a release branch by cherry-pick from `main`. A release branch is never merged into `main`.
- No other long-lived branch is created. Work that takes months lands on `main` in increments, behind a flag.

The `v0.6.13` branch is an independent fork of the 0.6 line. It follows its own life, is never merged into `main`, and nothing in this document applies to it. Leave it as it is.

## Keeping `main` releasable

The model only works if `main` can be released on any day, including by someone who has not followed the project for months. That rests on the checks below and on a few rules.

### Checks on every pull request

| Workflow         | What it verifies                                                                                                |
| ---------------- | --------------------------------------------------------------------------------------------------------------- |
| `Backend`        | pre-commit (Ruff, mypy, license headers) and `pytest` on Python 3.10 to 3.13, plus the `pixano-worker` tests    |
| `Frontend`       | ESLint, Prettier, `svelte-check`, Vitest, and the production build                                              |
| `Docker`         | The application and worker images build, the running container answers `/health`, and the compose files resolve |
| `Documentation`  | The Astro site builds, including the generated API reference                                                    |
| `License header` | The copyright header is present in `.py`, `.ts`, and `.svelte` files                                            |

A pull request merges only when the checks that ran have passed, with one approving review, and with every commit signed off (`git commit -s`).

### Rules

- A bug fix comes with a regression test that fails without the fix.
- New behavior comes with its tests in the same pull request.
- A change that is not ready for users goes behind a feature flag.
- When `main` is red, it is fixed or the offending commit is reverted the same day. Nothing else merges until it is green.

### Feature flags

- A flag defaults to off, so that a release without any configuration behaves like the previous one.
- The flag is documented where it is read, and tested in both states.
- A release is validated with every flag at its default value.
- The flag is removed once the feature is the default.

`ACTIVATE_UI_V1_0`, which keeps the new UI hidden, is the model to follow.

## Versioning

- `VERSION` at the repository root is the source of truth. When a pull request into `main` or a release branch changes it, the `Version` workflow copies the value into `src/pixano/__version__.py` and `ui/apps/pixano/package.json`.
- The `Publish` workflow refuses to publish unless the three values agree and the release tag is `v` followed by the content of `VERSION`.
- Versions follow [PEP 440](https://peps.python.org/pep-0440/): `X.Y.Z` for a release, `X.Y.ZrcN` for a release candidate, `X.Y.Z.dev0` for development.
- Between releases, `main` carries the next minor with a `.dev0` suffix: after `0.9.0` is released, `main` is at `0.10.0.dev0`. A build from `main` never reports a published version.
- Before 1.0, a minor version may break compatibility. A removal is announced under "Deprecated" in the changelog of the previous minor.
- A patch version contains fixes only: no new feature, no change to a dataset schema or to the REST API.

## Changelog and release notes

- `CHANGELOG.md` starts with an `## Unreleased` section. Each pull request that changes what users see adds a line to it, under "Added", "Changed", "Deprecated", "Removed", or "Fixed".
- At release, that heading becomes `## X.Y.Z (YYYY-MM-DD)`, and a new empty `## Unreleased` section is added when `main` is reopened.
- For a minor version, `docs/releases/X.Y.Z.md` holds a short summary for users: highlights, compatibility changes, known limitations. It becomes the body of the GitHub release. `docs/releases/0.8.0.md` is the example.
- For a patch version, the changelog section is the release body.

## When to release

Pixano is developed in bursts, with quiet periods in between, so there is no release calendar.

- A minor version ships when a burst of work ends. Release before the contributors move on: they are the ones who can validate the result and fix what the release uncovers.
- During an active period, release as soon as `main` has carried unreleased user-visible changes for about six weeks, even if more work is planned. Unfinished work stays behind its flag and ships later.
- A patch version ships as soon as a fix for the published version has landed, in any period.
- A quiet period needs no release.

## Releasing a minor version

Replace `X.Y.0` with the version being released.

### 1. Check that `main` is ready

- The latest runs on `main` are green: `gh run list --branch main --limit 10`.
- No open issue is marked as blocking the release.
- The `## Unreleased` section of `CHANGELOG.md` matches what was merged since the previous release: `git log --oneline v<previous>..origin/main`.
- The wheel builds, installs in a clean environment, and starts. These are the commands the `Publish` workflow runs:

  ```sh
  uv build
  python -m venv /tmp/pixano-smoke
  /tmp/pixano-smoke/bin/python -m pip install dist/pixano-*.whl
  /tmp/pixano-smoke/bin/python .github/scripts/smoke_wheel.py --expected-version "$(cat VERSION)"
  ```

- The application has been checked by hand, with every feature flag at its default, on a **copy** of a real data directory (opening a dataset can migrate it):
  - the server starts and lists the existing datasets with the right record counts;
  - a dataset opens, media display, and existing annotations render;
  - an annotation can be created, saved, and found again after a reload;
  - a dataset can be imported and exported.

### 2. Open the release pull request

```sh
git fetch origin
git switch -c chore/release-X.Y.0 origin/main
echo "X.Y.0" > VERSION
```

In the same branch:

- rename `## Unreleased` to `## X.Y.0 (YYYY-MM-DD)` in `CHANGELOG.md`;
- add `docs/releases/X.Y.0.md`.

Commit with `git commit -s -m "chore: release X.Y.0"` and open the pull request into `main`. The `Version` workflow pushes a commit to the branch that aligns the backend and frontend versions. Merge once the checks pass.

### 3. Publish

Create the GitHub release on the merged release commit, not on whatever `main` points to by then:

```sh
gh release create vX.Y.0 --target <sha of the release commit> --title "vX.Y.0" --notes-file docs/releases/X.Y.0.md
```

This creates the tag and starts the `Publish` workflow, which:

1. checks the versions, builds the wheel, smoke-tests it, and uploads it to PyPI;
2. deploys the documentation site;
3. pushes `pixano/pixano:X.Y.0` to Docker Hub and moves `pixano/pixano:stable` to it.

Follow it with `gh run watch`.

### 4. Verify

- `pip install pixano==X.Y.0` works in a clean environment, and `pixano --help` runs.
- `docker pull pixano/pixano:X.Y.0` works.
- <https://pixano.github.io/pixano> shows the new documentation.

### 5. Reopen `main`

Open a pull request that sets `VERSION` to the next development version (`X.(Y+1).0.dev0`) and adds an empty `## Unreleased` section at the top of `CHANGELOG.md`. Merge it before any other pull request.

## Releasing a patch version

Replace `X.Y.Z` with the version being released; `X.Y` is the latest minor.

1. **Fix on `main` first**, through a normal pull request with a regression test. The only exception is a bug whose code no longer exists on `main`: fix it directly on the release branch and say so in the pull request.

2. **Create the release branch** if this is the first patch of the minor:

   ```sh
   git fetch origin --tags
   git branch release/X.Y vX.Y.0
   git push -u origin release/X.Y
   ```

3. **Backport the fix** through a pull request into the release branch:

   ```sh
   git switch -c fix/PIX-<n>-backport origin/release/X.Y
   git cherry-pick -x -s <sha of the fix on main>
   gh pr create --base release/X.Y
   ```

4. **Prepare the release** in a second pull request into the release branch: set `VERSION` to `X.Y.Z` and add a `## X.Y.Z (YYYY-MM-DD)` section to `CHANGELOG.md`. The `Version` workflow aligns the backend and frontend versions.

5. **Publish** from the release branch, with the changelog section as the body:

   ```sh
   gh release create vX.Y.Z --target release/X.Y --title "vX.Y.Z" --notes "<changelog section>"
   ```

6. **Verify** as for a minor version.

7. **Copy the changelog section** for `X.Y.Z` into `CHANGELOG.md` on `main`, below `## Unreleased`.

When the next minor is released, `release/X.Y` receives no further patch. Its tags remain.

## Release candidates

A release candidate is optional. Use one when a minor is large enough to need a stabilization period while development continues.

1. At feature freeze, create `release/X.Y` from `main`, and reopen `main` at `X.(Y+1).0.dev0` as in step 5 above.
2. On the release branch, set the version to `X.Y.0rc1` and publish it as a pre-release:

   ```sh
   gh release create vX.Y.0rc1 --target release/X.Y --title "vX.Y.0rc1" --prerelease --generate-notes
   ```

   PyPI treats it as a pre-release, so `pip` installs it only with `--pre`, and the Docker image is pushed without moving `stable`.

3. Fixes follow the patch procedure: `main` first, then a cherry-pick.
4. When the candidate is good, set the version to `X.Y.0` on the release branch, publish `vX.Y.0` from it, and copy the changelog section to `main`.

## If a release is broken

- Do not delete or move the tag, and do not reuse the version number. PyPI refuses a second upload of the same version in any case.
- Fix on `main` and ship the next patch version. `0.7.1` followed `0.7.0` on the same day for this reason.
- If installing the broken version is harmful, yank it on PyPI, so that `pip` skips it unless it is requested by exact version, and say so in the notes of its GitHub release.

## Transition

This section lists what the repository still lacks relative to the process above. Remove each item when it is done, and the section when it is empty.

- **Public documentation.** During the transition the site was deployed from `main`, so it describes unreleased work. Re-running the `Documentation` job of the `v0.8.0` run of `Publish` restores the 0.8.0 documentation.
- **Changelog of the work in progress.** `main` carries the work that was developed on `dev/v0.9`, but `## Unreleased` in `CHANGELOG.md` has no entry for it.
- **0.8 line.** If 0.8 needs a patch, `release/0.8` is created from the `v0.8.0` tag. Its workflows still trigger on `releases/**`, so the first change on that branch has to switch them to `release/**`. The old `releases/0.8` branch has the same content as the tag but holds the detailed 0.8 history, which the squashed release commit on `main` does not: archive it as a tag before deleting it.
- **Required checks.** `main` requires one review but no status check. The workflows above have to be made required. They use path filters, and GitHub leaves a required check that was skipped pending forever, so the filters have to be handled at the same time.
- **Wheel smoke test.** `.github/scripts/smoke_wheel.py` runs only inside `Publish`, after the tag exists. It should run on pull requests.
- **Slow and end-to-end tests.** Tests marked `slow`, `hub`, and `e2e` never run in CI, and no test drives the UI in a browser. A scheduled run on `main` is needed, and the manual checks of step 1 should shrink as it grows.
- **Worker package.** `packages/pixano-worker` has its own version and no publication step in `Publish`. Whether it is released together with Pixano is still to be decided.
- **Merged branches.** GitHub does not delete a branch when its pull request merges; the setting should be turned on.
