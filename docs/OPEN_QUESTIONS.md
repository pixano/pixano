# Open questions

> A running list of undecided architecture / packaging questions. Add an entry
> when a decision is deferred; remove it (and record the outcome in the relevant
> doc or code) once resolved.

## Per-dataset layout preference — accepted limitations

**Status:** open (deliberate trade-offs, shipped knowingly).

The workspace remembers how a user arranges a dataset's widgets and replays it on
the dataset's other records (`ui/apps/web/src/lib/workspace/datasetLayout.ts`,
`datasetLayoutRepository.ts`; see FRONTEND_ARCHITECTURE.md §4). These limits were
accepted to keep the first version small — each is a decision, not an oversight.

- **Storage is browser-local.** The arrangement never follows a user across
  machines or browsers. `DatasetLayoutRepository` exists precisely so this can
  move to a user-scoped preference endpoint by swapping the implementation
  injected into `WorkspaceManager`, with no call-site changes.
- **No way to forget an arrangement.** `clear()` was dropped from the port when
  "Reset layout" was redefined as "restore what this record opened with", leaving
  no caller. Consequences: a dataset can never go back to purely automatic
  placement once arranged, and entries for deleted datasets linger in
  `localStorage`. Re-adding `clear()` plus a "Forget arrangement" action is the
  fix if either becomes a real complaint.
- **Only view-backed widgets are remembered.** A widget dragged in from the
  palette has no counterpart in the next record's views, so nothing would restore
  it onto. "Fit layout" does re-tile them on screen; they just are not persisted.
- **Concurrent tabs: last writer wins.** No `storage` event listener, so two tabs
  on the same dataset overwrite each other's arrangement.
- **The arrangement no longer adapts to the viewport.** Before this feature every
  record opened with a placement recomputed for the current screen. Once a
  dataset has been arranged, its records replay cell coordinates captured on
  whatever screen the user arranged them on, and nothing re-fits automatically —
  an arrangement built on a large display can extend past the fold on a laptop.
  "Fit layout" is the manual escape hatch; re-fitting on viewport change (or
  storing the viewport alongside the arrangement and re-planning when it differs
  markedly) is the fix if this bites.

## How should `tri3d` be declared for `uv`?

**Status:** open.

`tri3d` is used by `src/pixano/datasets/builders/folders/builder_3d.py`
(`Dataset3DBuilder`) to import tri3d-supported 3D datasets (nuScenes, Argoverse, …).
It is currently declared **nowhere** in `pyproject.toml`, so `uv sync` (core deps +
the default `test` group) never installs it — you must `pip install tri3d` by hand.

It is treated as **optional by design**: `datasets/builders/__init__.py` guards
`Dataset3DBuilder` behind `try/except ImportError`, and the builder test
`importorskip`s it, so the rest of Pixano works without it. The gap is only that
there is no *supported* install path.

Options:

- **A — opt-in (matches the current optional design).** Add a group to
  `[dependency-groups]`:
  ```toml
  [dependency-groups]
  threed = ["tri3d >= 0.2.0, < 0.3.0"]
  ```
  Install 3D support with `uv sync --group threed`. Keeps the default install light
  (`tri3d` pulls in `numba` + `llvmlite`).
- **B — installed by default.** Add `threed` to `[tool.uv] default-groups` (or put
  `tri3d` in core `dependencies`) so a plain `uv sync` installs it for everyone.
  Simplest for 3D users, but forces `tri3d` + `numba` + `llvmlite` into every
  install and softens the "optional" design.

**Leaning:** A (opt-in), but undecided — needs a team call. Whichever is chosen,
declaring it in `pyproject.toml` also removes the current manual `pip install`
step. Tested against `tri3d 0.2.2`.
