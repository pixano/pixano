# Changelog

## 0.8.0 (unreleased)

Two redesigns. The data import/export core
(`docs/specs/data-import-export.md`): one `analyze → plan → ingest` pipeline
shared by the CLI, the REST API, and Python. And the application: server-backed
search and filtering, semantic search, and a rebuilt explorer, workspace, and
library.

### Added

- **JSONL v2** — a strict, hand-authorable annotation format (`metadata.jsonl`
  per split + a `dataset.yaml` manifest). Unknown keys and kinds are errors
  with did-you-mean suggestions; nothing is inferred from value shapes.
- **`pixano data` CLI** — `import` (analyze plan + confirmation, `--dry-run`),
  `export` (`pixano_jsonl`, `coco`), `formats`, and
  `jobs list|show|cancel|resume|rollback`.
- **COCO** importer (two-pass streaming, SQLite spill for huge annotation
  files, `pixano[coco]` extra for ijson) and exporter with an id-traceable
  round-trip.
- **LeRobot** importer (v2.1 + v3): episodes become annotatable frame
  sequences sampled 1:1 with the data rows at their exact timestamps;
  `action`/`observation.state` land in a `timeseries` table with fixed-size
  vector columns; direct Hugging Face Hub import
  (`pixano data import ./data org/name --episodes 0:4`) is included in the default
  installation and downloads only metadata and the selected episodes' shards.
- **Durable jobs** — SQLite store shared by the API and the CLI, `/io/*` REST
  routes (formats/analyze/imports/exports/jobs), cooperative cancel, resume
  from the last committed checkpoint, and add-mode rollback through guarded
  version restoration. Rollback refuses datasets changed since the import and
  resumed imports; dataset write locks prevent interleaved edits during an add.
- **Atomic ingestion** — staged builds with journaled overwrite swaps
  (crash-safe at every step, replayed at boot), idempotent add-mode re-runs
  via deterministic ids, per-image grid previews stamped at import.
- **Media contract** — embed-in-LanceDB by default (self-contained datasets);
  `media: {mode: uri}` stores datalake URIs verbatim (S3/HTTP served by your
  infrastructure). Mixed datasets are legal and recorded as such.
- **Typed filters and server-side sort** — records are queried with repeated
  `filter=col:op:value` params plus a free-text `q`, compiled against a
  per-dataset column catalogue (`GET /datasets/{id}/filters`). Every column,
  operator, and value is allowlisted, so a malformed query is a 400 instead of
  raw SQL reaching the engine. Sorting runs server-side with a stable `id`
  tie-break, so pagination is exact across pages, and
  `GET /datasets/{id}/records/{record_id}/neighbors` gives
  prev/next/position/total within the active filter and sort.
- **Semantic search** — record-level image search: text → records, and "more
  like this" from any record. Embeddings are computed by the inference server,
  so no ML model ever loads in the Pixano process. Vectors live in a
  `RecordEmbedding` table with an `embeddings.json` sidecar, so the table opens
  without registering an embedding function and survives restarts and exports.
  Adds `POST /datasets/{id}/records/search`, a resumable
  `POST /datasets/{id}/embeddings/compute` job, and health and repair via
  `Dataset.record_embedding_health()` / `drop_record_embeddings()`.
- **Explorer** — a table and a gallery over that same query surface: typed
  filter chips, split/status facets, sortable columns with working column
  settings, a rows-per-page selector, and cards composed from whatever
  previews a record carries (single image, multi-view mosaic, video frame,
  text excerpt). Skeletons while loading, inline empty states with a
  clear-filters action, and rank/distance chips on ranked results.
- **Workspace shell** — one structure shared by the image, video, VQA, and MEL
  workspaces: an entity creator with a real combobox and an explicit
  `Create "…"` action, a Record tab holding record status and attributes,
  image display controls (brightness, contrast, channels, 16-bit) as a toolbar
  popover, and a breadcrumb header that continues the app's navigation with a
  record counter and a change-count Save button.
- **Library** — dataset groups (todo, new, favorite) as tabs over a full-width
  grid with a pinned toolbar, per-dataset split/status counts and progress
  bars, sorting, and search.
- **Inference panel** — registered servers and their deployed models, grouped
  by task, reachable from a status chip in the app header on every page
  (previously a sidebar on the library page only).
- **Resizable previews** — `?size=` (128, 256, or 512) on the image and
  sequence-frame preview routes, resized on demand from the stored blob with
  size-varying ETags; text views expose a short excerpt, so text and MEL
  records have real content in lists and cards.

### Changed

- The dataset manifest is `dataset.yaml` (name, workspace, format, media
  policy, schema) — auto-discovered at the source root.
- Import formats auto-detect; format-intrinsic schemas (COCO, LeRobot) apply
  automatically and default their natural UI workspace.
- The import wizard uses one Setup screen with Source and Annotation panels,
  followed by Review. Format icon cards sit in Source; task icon cards sit above
  annotation tools and the compact attribute table. LeRobot shows a fixed video
  task. Desktop panels scroll independently and stack on mobile; optional metadata
  and Advanced JSON are collapsed. Edit setup preserves uploaded sources and
  annotation settings. Required video tracks, Q&A, and text spans appear as quiet
  Included labels; keypoints, relations, and classification are not offered in the
  setup form. Imported schemas and backend format support are unchanged.
- Starting an import closes the wizard once the server accepts the job. The
  jobs tray shows progress, completion, errors, and cancellation; start-request
  failures stay on Review for retry.
- The inference integration is rebuilt on `pixano-inference-client` against the
  server's `/v1` API. A single `/inference` surface replaces `/app/inference/*`,
  and the task vocabulary is now `image_mask_generation`,
  `video_mask_generation`, `detection`, `vlm`, `ner`, and `embedding` (was
  `Segmentation*` and `Tracking*`). `pixano-inference-client` is pinned to the
  published PyPI release `0.1.0`.
- One visual system across library, explorer, and workspace: semantic color
  tokens, glass surfaces, and a single control dialect.

### Deprecated (removal in 0.9)

- `DatasetBuilder` — implement a `pixano.datasets.io.DatasetImporter` instead
  (test harness in `pixano.datasets.io.testing`).
- The GUI import alias `POST /datasets/import` + `GET /datasets/import/{id}`
  — retained for compatibility; the import wizard uses `/io/*`.

### Removed

- The 0.7 folder builders (`ImageFolderBuilder`, `VideoFolderBuilder`,
  `VQAFolderBuilder`, `MelFolderBuilder`), the v1 metadata heuristics and
  alias tables, `mosaic.py`, and the superseded JSONL exporter. Imports require
  JSONL v2; no legacy JSONL converter is shipped.

### Fixed

- Dependency validation uses stable releases, removes unused runtime packages,
  and updates affected packages to patched versions. FastAPI's minimum matches
  the template API used by the application.
- Docker installs the wheel's dependencies from PyPI without development or
  test packages, validates their compatibility, and bundles the license text.
- Source distributions include only package sources, tests, and build files,
  excluding local datasets and other untracked files outside those directories.
- COCO export converts `xyxy` and `xywh` bounding boxes to pixel-space `xywh`
  coordinates and computes the corresponding areas correctly.
- Imports reject changed sources or settings before using a saved plan or resuming
  a checkpoint. Local checks cover file metadata and referenced media; Hub downloads
  use a pinned commit. Legacy checkpoints without source verification require a restart.
- The LeRobot import wizard exposes object and record attributes and annotation
  types. Custom schemas retain discovered cameras, episode metadata, and
  state/action vectors through analysis and import. The annotation editor
  respects required fields, schema defaults, and typed list attributes.
- Interrupted LeRobot imports retain the correct episode cursor; Arrow and
  final buffered batches persist complete checkpoints. CLI imports use the
  same durable job identity as their staging data, and failed resumable jobs
  keep their staging and uploaded sources after server restart.
- Annotation saves acknowledge each completed operation and preserve later
  edits. Repeating an identical create request is safe after a lost response;
  conflicting content for the same ID returns 409 without overwriting it.
- Unsaved annotations are protected when leaving through the logo, links,
  browser history, and record navigation.
- Rapid record navigation no longer uses stale neighbors, and attribute
  dropdowns sort their options without mutating reactive data.
- Docker publication waits for the PyPI release. Package publication first
  verifies installation and startup of the built wheel in a clean environment.
- Explorer column settings changed nothing: the TanStack adapter eagerly
  spread the Svelte `$state` getters, so the table never depended on column
  order or visibility and never re-rendered. State is now merged through a
  lazy getter-forwarding proxy.
- The Tailwind theme registered only nine color utilities, so
  `text-muted-foreground`, `text-primary-foreground`, `text-destructive`, the
  surface backgrounds, and every elevation shadow generated no CSS anywhere in
  the application.
- A corrupt embeddings sidecar raised out of `Dataset.__init__` and made every
  endpoint of that dataset return 500. It now degrades to "no embeddings", a
  degraded store answers 503 or 409 with actionable detail instead of 500, and
  a forced recompute drops and rebuilds it.
- `to_sql_list` did not escape single quotes, and the view-preview query
  materialised every frame of every video.
- Save failures in the workspace were reported only to the console; they now
  surface as an inline banner.

### Known limitations

- Import progress is not restored after a browser refresh; jobs remain available
  through the CLI/API. Expired review plans prevent resuming affected jobs after
  24 hours. Abandoned uploads are collected during server startup.
- LeRobot datasets do not support a complete Pixano JSONL export/re-import in
  0.8: time-series data are omitted, and exported annotation schemas can be
  incomplete. This is deferred to 0.9; JSONL export is not a LeRobot backup format.
- AV1 video shards decode fine for frame extraction but do not play in
  Safari (upstream codec support).
- 3D features (bbox3d, keypoints3d, camera calibration) are deferred to 0.9.
- Semantic search indexes image records and supports text-to-image queries.
  Indexing text records and per-view embeddings are deferred to 0.9.
- The inference server registry is held in memory: registered servers are lost
  when the backend restarts and must be connected again.
