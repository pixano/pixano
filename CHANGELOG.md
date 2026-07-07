# Changelog

## 0.8.0 — 2026-07-07

The data import/export redesign (`docs/specs/data-import-export.md`): one
`analyze → plan → ingest` core shared by the CLI, the REST API, and Python.

### Added

- **JSONL v2** — a strict, hand-authorable annotation format (`metadata.jsonl`
  per split + a `dataset.yaml` manifest). Unknown keys and kinds are errors
  with did-you-mean suggestions; nothing is inferred from value shapes.
  Import → export → import is id-identical.
- **`pixano data` CLI** — `import` (analyze plan + confirmation, `--dry-run`),
  `export` (`pixano_jsonl`, `coco`), `formats`, `migrate-jsonl` (0.7 → v2
  converter; everything 0.7 guessed becomes an explicit needs-attention note),
  and `jobs list|show|cancel|resume|rollback`.
- **COCO** importer (two-pass streaming, SQLite spill for huge annotation
  files, `pixano[coco]` extra for ijson) and exporter with an id-traceable
  round-trip.
- **LeRobot** importer (v2.1 + v3): episodes become annotatable frame
  sequences sampled 1:1 with the data rows at their exact timestamps;
  `action`/`observation.state` land in a `timeseries` table with fixed-size
  vector columns; direct Hugging Face Hub import
  (`pixano data import ./data org/name --episodes 0:4`, `pixano[lerobot]`
  extra) downloads only the metadata and the selected episodes' shards.
- **Durable jobs** — SQLite store shared by the API and the CLI, `/io/*` REST
  routes (formats/analyze/imports/exports/jobs), cooperative cancel, resume
  from the last committed checkpoint, and add-mode rollback (version restore,
  or a namespace-scoped delete that preserves concurrent edits).
- **Atomic ingestion** — staged builds with journaled overwrite swaps
  (crash-safe at every step, replayed at boot), idempotent add-mode re-runs
  via deterministic ids, per-image grid previews stamped at import.
- **Media contract** — embed-in-LanceDB by default (self-contained datasets);
  `media: {mode: uri}` stores datalake URIs verbatim (S3/HTTP served by your
  infrastructure). Mixed datasets are legal and recorded as such.

### Changed

- The dataset manifest is `dataset.yaml` (name, workspace, format, media
  policy, schema) — auto-discovered at the source root.
- Import formats auto-detect; format-intrinsic schemas (COCO, LeRobot) apply
  automatically and default their natural UI workspace.

### Deprecated (removal in 0.9)

- `DatasetBuilder` — implement a `pixano.datasets.io.DatasetImporter` instead
  (test harness in `pixano.datasets.io.testing`).
- The GUI import alias `POST /datasets/import` + `GET /datasets/import/{id}`
  — still served (backed by the shared job store) until the import wizard
  replaces the modal.

### Removed

- The 0.7 folder builders (`ImageFolderBuilder`, `VideoFolderBuilder`,
  `VQAFolderBuilder`, `MelFolderBuilder`), the v1 metadata heuristics and
  alias tables, `mosaic.py`, and the superseded JSONL exporter. Use
  `pixano data migrate-jsonl` to convert 0.7 sources.

### Known limitations

- AV1 video shards decode fine for frame extraction but do not play in
  Safari (upstream codec support).
- 3D features (bbox3d, keypoints3d, camera calibration) are deferred to 0.9.
