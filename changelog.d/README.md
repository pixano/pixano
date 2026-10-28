# Changelog fragments

Each pull request that changes what users see adds one file here instead of editing
`CHANGELOG.md`. The release gathers them into `CHANGELOG.md` and deletes them (see
`RELEASING.md`).

Name the file after the Linear issue and the kind of change:

- `PIX-<n>.added.md`, `PIX-<n>.changed.md`, `PIX-<n>.deprecated.md`, `PIX-<n>.removed.md` or
  `PIX-<n>.fixed.md`;
- `+<short-name>.<type>.md` when there is no issue.

The file holds the entry as Markdown, written for users: what changes for them, not how the
code changed. For example, `PIX-172.fixed.md`:

```markdown
The legacy app finds the bounds of a mask whose first pixel is painted, as a SAM mask can be.
Such a mask got inverted bounds, and a wrong box around it.
```

Preview the next release's section with `uvx towncrier build --draft --version X.Y.Z`.
