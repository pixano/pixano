# Issue tracking

For the Pixano team and its agents. [`AGENTS.md`](../AGENTS.md) sends you here before you file an issue, start work on one, or open a pull request for one.

## Where issues live

Team issues are private. They live in the private repository `pixano/pixano-project-manager` and on the org project "Pixano". Elsewhere they are named `PM-<n>`, and an autolink on `pixano/pixano` turns `PM-<n>` into a link. Issues on the public `pixano/pixano` are reports from outside the team.

Linear holds the `PIX-<n>` issues opened before 2026-11-22. They are finished there, but no issue is created in Linear any more. A follow-up of a `PIX-<n>` issue is a new `PM-<n>` issue that says "Follow-up of PIX-<n>".

## Privacy

- Open a team issue only in `pixano/pixano-project-manager`, never on `pixano/pixano`. If one is opened there by mistake, move it with `gh issue transfer <n> pixano/pixano-project-manager`.
- Never copy the text or the discussion of a private issue into a public pull request, commit, issue or changelog entry. Name it `PM-<n>`.

## Filing an issue

```sh
gh issue create -R pixano/pixano-project-manager --project Pixano --type Task \
  --title "[Theme] What changes" --body-file issue.md
```

- **Type:** `Task`, `Bug` or `Feature`.
- **Title:** starts with its theme in brackets.
- **Agent notes:** the details for agents go at the end of the body, in a `<details><summary>Agent notes</summary>…</details>` block.
- **Parent:** attach an issue to its parent:

  ```sh
  id=$(gh api repos/pixano/pixano-project-manager/issues/<child> -q .id)
  gh api -X POST repos/pixano/pixano-project-manager/issues/<parent>/sub_issues -F sub_issue_id=$id
  ```

`--project` needs the `project` scope of the `gh` token: `gh auth refresh -s project`.

## Working on an issue

- **Worktree and branch:** named after the issue, as in `git worktree add ../PM-<n> -b feat/PM-<n> origin/main`. An issue still in Linear keeps `PIX-<n>`.
- **Changelog fragment:** named after the issue, as in `PM-<n>.fixed.md` (see [`changelog.d/README.md`](../changelog.d/README.md)). The released changelog does not show the issue.
- **Pull request:** the title ends with `(PM-<n>)`. The body says `Fixes pixano/pixano-project-manager#<n>`: only that full reference closes the private issue when the pull request merges, and `PM-<n>` alone is just a link.
