# Repository Guidelines

## Project Overview

Pixano is an open-source data engine for multi-modal AI development. It provides tools for dataset annotation, exploration, and curation, with workflows assisted by AI agents.

## Project Structure & Module Organization

Pixano is a web application organized as a monorepo with a backend server and a UI frontend. The backend is a Python application following standard `uv` package conventions under `src/pixano/`. The `ui/` directory is a pnpm + Turbo workspace holding two frontend applications, both bundled into the wheel by `hatch_build.py`:

- `ui/apps/web` (package `@pixano/web`) — the **new workspace UI**, built on a plugin annotation architecture. This is where current frontend work happens; `docs/FRONTEND_ARCHITECTURE.md`, `docs/ARCHITECTURE_TOOLING.md`, `docs/CODING_STANDARDS.md` and `docs/ADDING_AN_ANNOTATION_KIND.md` all describe this app and only this app.
- `ui/apps/pixano` — the **legacy app** (`hatch_build.py` calls it the "legacy frontend"), being migrated away from. Do not add features here.

There is no `ui/packages/` directory; the two apps share no code (`restTypes.ts` / `apiClient.ts` are hand-copied between them). The documentation website is built with Astro and lives in `docs-astro/`.

Backend modules are organized as follows:

- `src/pixano/api`: REST API module with FastAPI routers.
- `src/pixano/cli`: Pixano CLI module.
- `src/pixano/datasets`: LanceDB dataset engine and Python API. `datasets/io/` holds the 0.8.0 import/export engine (`formats/{pixano_jsonl,coco,lerobot}`); the v1 folder builders were removed in that redesign.
- `src/pixano/inference`: adapters for AI model inference services.
- `src/pixano/features`: annotation feature definitions.
- `src/pixano/schemas`: Pixano database schemas.
- `src/pixano/utils`: shared utilities.
- `tests`: unit and e2e test modules.

Design specifications live in `docs/specs/`. Before planning or implementing changes to dataset import/export, read [docs/specs/data-import-export.md](./docs/specs/data-import-export.md) — the accepted architecture reference for the 0.8.0 data import/export redesign.

## Tech Stack

The backend uses FastAPI for the server, LanceDB as the dataset engine, Python for implementation, and `uv` for dependency management and builds. The frontend uses SvelteKit, Svelte 5, TypeScript, and `pnpm`. UI libraries differ per app: `ui/apps/web` uses Tailwind CSS, bits-ui, Konva, Three.js with Threlte, Tiptap and lucide-svelte; the legacy `ui/apps/pixano` uses Tailwind CSS, bits-ui, Konva with svelte-konva, D3/Chart.js, ONNX Runtime Web, Tiptap and phosphor-svelte.

## Build, Test, and Development Commands

Pixano is shipped as a pip-installable package that bundles the frontend build artifacts. Installed users can initialize a fresh data directory and run the app through the Pixano CLI:

```sh
pixano init /path/to/data
pixano server run /path/to/data
```

When using an existing initialized Pixano data directory, skip the initialization step and run only:

```sh
pixano server run /path/to/data
```

For backend development, install dependencies and initialize a fresh data directory from the repository root:

```sh
uv sync
uv run pixano init /path/to/data
uv run pixano server run /path/to/data
```

When using an existing initialized Pixano data directory during backend development, skip the initialization step and run only:

```sh
uv run pixano server run /path/to/data
```

For frontend development, start the dev server for the app you are working on:

```sh
cd ui
pnpm install
pnpm run dev:web      # the new workspace UI (ui/apps/web) — the usual target
pnpm run dev:pixano   # the legacy app (ui/apps/pixano)
```

Run backend tests with `uv run pytest --cov=src/pixano tests/`. Run frontend tests with `pnpm -C ui test` (Turbo, both apps) or `pnpm -C ui/apps/web test` for the new UI alone — note `pnpm -C ui/apps/pixano test` covers only the legacy app. Type-check the new UI with `pnpm -C ui/apps/web run check`. For broader checks, use `uv tool run pre-commit run --all-files`, `pnpm -C ui lint`, and `pnpm -C ui format_check`.

For release builds, just build the Python wheel:

```sh
uv build
```

`hatch_build.py` runs `pnpm install --frozen-lockfile` and then builds **both** frontends (legacy then web) as part of the wheel build, so there is no separate UI step. It is skipped for editable installs — build the app you need by hand there (`pnpm -C ui/apps/web run build`).

## Coding Style & Naming Conventions

Python uses Ruff for linting and formatting, with a 119-character line limit, double quotes, and Google-style docstrings. Use `snake_case` for Python modules and functions, and `PascalCase` for classes.

Frontend code uses TypeScript, Svelte 5, ESLint, and Prettier. Name Svelte components `PascalCase.svelte`, helpers `camelCase.ts`, and Vitest files `*.test.ts` under `src/**/__tests__/`. Preserve the repository copyright header in `.py`, `.ts`, and `.svelte` files.

UI text is written as literal strings. Neither app has an i18n layer and none is planned — there is no translation module, no message catalogue and no key indirection. Write the string where it is displayed.

## Testing Guidelines

Add or update tests alongside the code you change. Backend tests should use `test_*.py` names under the matching `tests/` area. Frontend tests should stay colocated in `__tests__` directories. Tests marked `e2e` require a live inference server configured with `PIXANO_INFERENCE_URL`.

## Git Workflow

### Committing Changes

When committing changes:

- Use short, imperative commit subjects. Recent history commonly uses conventional prefixes such as `fix:`, `feat:`, `docs:`, `refactor:`, `ci:`, and `chore:`. Keep commits focused on one logical change.
- DCO sign-off: All commits MUST use the `-s` flag (otherwise CI will reject them)
- Do NOT add `Co-Authored-By` trailers (or any other co-author lines) to commit messages.
- Pre-commit hooks: Run before committing (see [Pre-commit Hooks](#pre-commit-hooks))

```bash
# Commit with required DCO sign-off
git commit -s -m "Your commit message

# Push your changes
git push origin <your-branch>
```

### Creating Pull Requests

- Follow the instructions at the top of [the PR template](./.github/pull_request_template.md) carefully.
- Inside `gh pr ... --body "$(cat <<'EOF' ... EOF)"`, write backticks plain. The quoted `'EOF'` delimiter already suppresses command substitution, so escaping as `` \` `` is unnecessary and the backslashes get persisted in the PR body, rendering literally instead of as code spans.

  ```bash
  gh pr create --body "$(cat <<'EOF'
  Updated \`pyproject.toml\` to bump the version. # BAD
  Updated `pyproject.toml` to bump the version.   # GOOD
  EOF
  )"
  ```

### Checking CI Status

Use GitHub CLI to check for failing CI:

```bash
# Check workflow runs for current branch
gh run list --branch $(git branch --show-current)

# View details of a specific run
gh run view <run-id>

# Watch a run in progress
gh run watch
```

## Pre-commit Hooks

The repository uses pre-commit for code quality. `pre-commit` is not a project dependency, so install and run it locally as a `uv` tool:

```bash
uv tool install pre-commit
uv tool run pre-commit install --install-hooks
```

Run pre-commit manually:

```bash
# Run on all files
uv tool run pre-commit run --all-files

# Run on specific files
uv tool run pre-commit run --files path/to/file.py

# Run a specific hook
uv tool run pre-commit run ruff --all-files
```

This runs Ruff, formatting, license-header, and other configured hooks automatically before commits. Some hooks can rewrite tracked files; inspect `git status --short` after running them.
