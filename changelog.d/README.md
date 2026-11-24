# Changelog fragments

Each pull request that changes what users see adds one file here instead of editing
`CHANGELOG.md`. The release gathers them into `CHANGELOG.md` and deletes them (see
`RELEASING.md`).

Name the file after the issue and the kind of change:

- `PM-<n>.added.md`, `PM-<n>.changed.md`, `PM-<n>.deprecated.md`, `PM-<n>.removed.md` or
  `PM-<n>.fixed.md`;
- `PIX-<n>.<type>.md` for an issue still in Linear;
- `+<short-name>.<type>.md` when there is no issue.

The changelog shows the issue ID as plain text, without a link: the team's issues are private.

The file holds the entry as Markdown, written for users: what changes for them, not how the
code changed. Never copy the text of the private issue into it. For example, `PIX-172.fixed.md`:

```markdown
The legacy app finds the bounds of a mask whose first pixel is painted, as a SAM mask can be.
Such a mask got inverted bounds, and a wrong box around it.
```

Preview the next release's section with `uvx towncrier build --draft --version X.Y.Z`.
