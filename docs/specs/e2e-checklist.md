# 0.8.0 Import/Export — Manual End-to-End Validation Checklist

Companion to [data-import-export.md](./data-import-export.md). The redesign lands as a PR
stack on `arch/data-import`; nothing merges to `main` until every checkpoint below has been
validated by hand. Automated gates (full pytest suite locally and in CI on every PR) run
first — this checklist covers what automation cannot: a human confirming the real app
behaves correctly on real data.

**Always test on a COPY of a library, never the original.** Opening a dataset with 0.8.0
code performs a one-time additive migration (stamps `spec_version: 2` in `info.json` and,
for datasets with a `videos` table, backfills the `from_timestamp`/`to_timestamp` columns).
It is tested — including under concurrent opens — but a copy keeps working data untouched
and lets you diff the directory afterwards.

```sh
# Common setup for every checkpoint
cd /path/to/data-import-audit                # the redesign checkout
git checkout <branch under test> && uv sync
cp -R /path/to/real/data-dir /tmp/pixano-e2e # data dir = the folder holding library/
uv run pixano server run /tmp/pixano-e2e --port 7981
```

## Checkpoint A — "Nothing broke" (after the P0/P1 plumbing PRs)

The stack so far is additive plumbing: behavior must be identical to `arch/data-import`.

- [ ] Server starts; `GET /health` returns `{"status":"ok"}`.
- [ ] `GET /datasets` lists every dataset from the copy with correct `num_records`;
      payloads now include `spec_version: 2`.
- [ ] Browse a dataset in the UI: records grid, image display, existing annotations render.
- [ ] Create + save an annotation (bbox on an image); reload; it persisted.
- [ ] `info.json` in the copy gained only `spec_version` (diff against the original).
- [ ] For a dataset with videos: rows show `from_timestamp: 0.0` / `to_timestamp: -1.0`
      defaults and nothing else changed.

## Checkpoint B — new import CLI + JSONL v2 (after the P2 PRs)

- [ ] `pixano data import /tmp/pixano-e2e ./some_source --dry-run` prints a plan
      (counts, schema, findings) and writes nothing.
- [ ] A malformed line (unknown key/kind) fails with a `file:line` error and a
      did-you-mean suggestion; a v1-format file fails pointing at `migrate-jsonl`.
- [ ] Full import → dataset browsable in the UI (records, media, annotations).
- [ ] `pixano data export … --format pixano_jsonl` then re-import → same record count,
      same ids.
- [ ] Re-running the same import with `--mode add` does not duplicate rows.
- [ ] `pixano data migrate-jsonl` converts one of your existing v1 metadata.jsonl files.

## Checkpoint C — COCO + LeRobot (after the P3 PRs)

- [ ] Import a real COCO detection/segmentation set; spot-check boxes/masks against
      the source; export back to COCO; counts and categories survive.
- [ ] Import a LeRobot dataset (hub uri mode: metadata only, fast; local: embed with the
      size estimate shown in the plan first).
- [ ] Episode records browsable; a video window plays in the browse view (H.264 sets;
      AV1 limitation is documented behavior, not a bug).
- [ ] Import with `episodes:` subset selection; count matches.

## Checkpoint D — GUI import (after the P4 PRs)

- [ ] The legacy import modal still works exactly as in 0.7.x (deprecated alias).
- [ ] New wizard: pick format → analyze shows findings + preview → confirm → progress
      percentage advances → dataset appears without a server restart.
- [ ] Kill the server mid-import; restart; the job shows `interrupted`; resume completes
      with no duplicate rows (compare counts against an uninterrupted control run).

## Checkpoint E — release candidate (before `arch/data-import` → `main`)

- [ ] Build the installable artifact (`pnpm run build` in `ui/apps/pixano`, then
      `uv build`); install the wheel in a fresh venv; repeat Checkpoint A + B against it.
- [ ] Full soak on a complete copy of production data: every dataset opens, browses,
      annotates, saves.
- [ ] `uv run pytest --cov=src/pixano tests/` fully green, including `-m slow`.
- [ ] Changelog and migration guide reviewed.

Sign-off on E is the trigger for the single merge of `arch/data-import` into `main`.
