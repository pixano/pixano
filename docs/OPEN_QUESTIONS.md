# Open questions

> A running list of undecided architecture / packaging questions. Add an entry
> when a decision is deferred; remove it (and record the outcome in the relevant
> doc or code) once resolved.

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
