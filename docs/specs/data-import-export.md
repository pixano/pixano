# Pixano 0.8.0 — Data Import/Export Architecture Specification

**Status:** Accepted — reference for implementation planning.
**Scope:** the complete redesign of dataset import and export for the 0.8.0 release (formerly planned as 0.7.3; renumbered — see §14.1).
**Scope amendment (2026-07-05):** all 3D-related features are deferred to release 0.9 — the `bbox3d`/`keypoints3d` canonical families and slots, the `cam_calibration` view family with its `target_logical_name` binding and validator fixes, and the backend `WorkspaceType.PCL_3D` enum value. Dedicated 3D work is ongoing on a separate branch and 0.8.0 must not create conflicts or breaking changes there. `classification` and `relation` stay in 0.8.0 (general annotation types, not 3D). Sections referencing the deferred items are annotated in place.

**Provenance:** produced from a full audit of the current codebase, the pixano-cookbook, the LeRobot dataset format (v2.1/v3.0), and the importer architectures of huggingface/datasets, FiftyOne, and tensorflow/datasets; three independent architecture proposals were adversarially reviewed and synthesized into this document. All `file:line` references were verified against the `arch/data-import` branch.

---

## 1. Motivation & audit summary

Pixano users today face high friction importing data, and the implementation cannot support the 0.8.0 goals (GUI import sharing a core with the CLI, LeRobot/COCO builders, document/VQA/multimodal workspaces, large datasets). The audit found:

- **Closed, hardcoded dispatch.** `WorkspaceType` (4 values) maps to builder classes through a static dict (`src/pixano/cli/data.py:38-50`). There is no registry or plugin system; adding a LeRobot or COCO builder requires a new enum value, a new builder, a new dict entry, and frontend workspace support — a cross-cutting change, not an additive one.
- **The import spec is arbitrary Python.** `--info file.py:attr` executes a user `.py` file (`cli/_schema_loader.py:38-43`). This is unusable from a GUI and, per the cookbook audit, ~90% identical boilerplate across recipes — including empty ritual subclasses (e.g. `DAVISEntityDynamicState`).
- **The JSONL metadata format is under-specified**, so the code compensates with a heuristic normalization machine (`builders/folders/metadata.py`: alias maps `:161-191`, payload-shape key inference `:193-212`, alternate `views`/`annotation_files`/`entities` structures `:497-520`). The same dataset can be written at least four ways; docs contradict code (the documented MEL `text_span: [4,16]` form does not parse — `factories.py:305-359`); preflight validates with `json.loads` per line while build parses with `pyarrow.json.read_json` (`folder_base_builder.py:785`) — a row that passes preflight can be reshaped at build time.
- **Three annotation encodings coexist**: inline `entities[].annotations.<view>.<kind>`, mask-PNG globs, and per-frame JSON sidecars with `track_id` — none inferable from another, only one partially documented.
- **Media handling is undesigned.** Folder import force-sets `storage_mode="embedded"` (`folder_base_builder.py:127`) and reads every image into `raw_bytes`. Real video files are unimportable (the `is_video` uri branch is dead code — `VideoFolderBuilder` declares `SequenceFrame`); the GUI video import decodes every frame to JPEG and embeds them (`api/routers/import_datasets.py:159-197`). Import even mutates the user's source directory (mosaic writes JPEGs into it — `utils/mosaic.py:116-119`).
- **No scale story.** Build materializes whole metadata files in memory; there is no atomicity (a crash leaves a half-populated dataset dir that `create` mode then refuses), `add` mode duplicates rows on re-run, no resumability, no progress totals, and export runs O(records × tables) per-record scans (`exporters/dataset_exporter.py:87-106,130`).
- **The GUI import is a divergent prototype**: in-memory `_jobs` dict + daemon thread (`import_datasets.py:53,233`), a symlink hack to fake a `val` split, hardcoded schemas, and the rich preflight report discarded (`:127-129`).
- **Export is asymmetric and orphaned**: exporters have no CLI or API surface, and the exported JSONL shape (flat table-keyed DB rows) differs from the import `metadata.jsonl` shape — **no round-trip is possible**.
- **Data-model gaps**: `CamCalibration`, `BBox3D`, `KeyPoints3D`, `Classification`, `Relation` exist as schema classes but have no canonical table or `DatasetInfo` slot (`schemas/table_names.py:34-64` vs `schema_group.py:60-92`) — a concrete blocker for nuScenes-style datasets; `Video` has no time-window addressing — a blocker for LeRobot v3, whose mp4 shards contain many episodes.

**What the audit confirmed is worth keeping** (and this design builds on):

- `Dataset.add_records` — FK-dependency-ordered multi-table insert with cross-table pending-id resolution (`datasets/dataset.py:896-971`).
- The canonical resource-family registry — the single source of truth mapping slot ↔ resource ↔ table ↔ schema group ↔ base schema (`schemas/table_names.py:34-64`).
- `DatasetInfo`'s declarative slot/view model with its diff-based JSON schema serialization (`datasets/dataset_info.py`, `datasets/dataset_schema.py`).
- The preflight validation report UX — aggregated findings with sample locations, `--dry-run`, strict mode (`builders/folders/metadata.py:43-109`, CLI rendering `cli/data.py:124-148`).
- `DatasetExporter`'s three-method authoring contract (`exporters/dataset_exporter.py:52-85`).
- `TableQueryBuilder`, `ViewFamilyIntegrityValidator`, `create_instance_of_schema`.

## 2. Goals & non-goals

### Goals (0.8.0)

1. **One shared import/export core** (`src/pixano/datasets/io/`) used identically by the CLI, the REST API/GUI, and the Python API.
2. **A declarative import spec** (YAML/JSON/CLI flags/GUI form) replacing `--info file.py:attr` for the common cases; custom Python importers remain a first-class advanced path (CLI/Python only — the REST API never executes user Python).
3. **One rationalized, documented JSONL annotation format (v2)** users can author by hand — strict validation, no aliases, no shape inference, excellent error reporting.
4. **Three built-in formats**: `pixano_jsonl` (import+export), `coco` (import+export, round-trip), `lerobot` (import: v2.1+v3.0, local dir + HF hub).
5. **Two media storage modes, embed by default**: raw bytes embedded in LanceDB tables, or user-served URIs for datalake-resident data (§6).
6. **Production-grade ingestion**: streaming, batched (Arrow-native where hot), deterministic/idempotent IDs, atomic create/overwrite, manifest-journaled add, resumable, cancellable, with real progress totals and a durable job store shared by CLI and GUI.
7. **First-class video**: `Video` views with time-window addressing; no forced frame explosion.
8. **Close the orphan-schema gap for 2D**: canonical tables/slots for classification and relations. *(The 3D half — calibration, 3D boxes/keypoints — is deferred to 0.9; see the scope amendment.)*
9. **Export symmetry**: `pixano_jsonl` export emits exactly the import grammar (id-equal round-trip in CI); COCO round-trips semantically; export gets CLI and API surfaces.

### Non-goals (0.8.0) — extension points ready, deliberately out

nuScenes importer · `pixano data convert` · HF `imagefolder` compatibility shim · merge-by-key annotation re-import · SSE/WebSocket progress · Lance blob-encoding storage class (spike scheduled, §14.3) · LeRobot exporter · browser file upload (GUI import takes server-visible paths and URIs) · frame-accurate video annotation player (0.8.x workstream; 0.8.0 ships video *browse*) · AV1 transcoding · sensor-series tables for state/action curves · **all 3D data-model work** (`bbox3d`/`keypoints3d` families, `cam_calibration` family + binding, `PCL_3D` workspace, nuScenes readiness) — deferred to 0.9 to avoid conflicts with the separate 3D workstream branch.

## 3. Architecture overview

Layered `analyze → plan → ingest` pipeline. Entry points build the same declarative spec; a format registry dispatches to format-layer importers/exporters; a single engine owns all writes.

```
┌────────────────────────────── ENTRY POINTS ───────────────────────────────────┐
│ CLI                          REST API / GUI                Python API         │
│ src/pixano/cli/data.py       src/pixano/api/routers/       pixano.datasets.io │
│  import/export/jobs/formats   data_io.py  (/io/*)           import_dataset()  │
│  migrate-jsonl                videos routes in views.py     analyze()         │
│                                                             export_dataset()  │
└──────────────┬───────────────────────┬────────────────────────────┬───────────┘
               └── all three build the same ImportSpec / ExportSpec ┘
                                       ▼
┌───────────────────────── FORMAT REGISTRY  io/registry.py ─────────────────────┐
│ DataFormat {name, importer_cls?, exporter_cls?, params_model, capabilities,   │
│             detect()}   FORMATS: built-ins ∪ entry_points("pixano.formats")   │
└──────────────┬────────────────────────────────────────────────────────────────┘
               ▼ one importer/exporter instance per job
┌──────────────────────── FORMAT LAYER  io/formats/ ────────────────────────────┐
│ pixano_jsonl/ (import+export, incl. media-only folders)  coco/ (import+export)│
│ lerobot/ (v2.1 + v3.0, local + HF hub, import-only)                           │
│ Contract: DatasetImporter — probe() / analyze() → ImportPlan /                │
│           iter_batches(plan, cursor) → Iterator[BatchBundle]                  │
│ Custom Python: subclass DatasetImporter (CLI --importer file.py:Class or      │
│ installed entry point; REST refuses file-path Python)                         │
└──────────────┬────────────────────────────────────────────────────────────────┘
               ▼ BatchBundle = {tables: dict[str, list[LanceModel]]            (row path)
               │                       | dict[str, pa.RecordBatch],            (Arrow path)
               │                cursor: Cursor, provenance: Provenance}
┌──────────────────────── IMPORT ENGINE  io/engine.py ──────────────────────────┐
│ ImportEngine — the ONLY writer:                                               │
│  · IdLedger (cross-flush id/FK state; no per-flush DB scans on fresh builds)  │
│  · byte- and row-bounded per-table buffering                                  │
│  · create/overwrite → build in <data_dir>/.pixano/staging/, atomic rename;    │
│    trash outside library/; swap journal; dataset-cache invalidation hook      │
│  · add → ImportManifest first, writes via Dataset.merge_records (upsert)      │
│  · scalar-index creation (id, record_id) at finalize                          │
│  · flush-boundary checkpoints → resume; ProgressEvent fan-out                 │
│ RecordBundleReader (io/reader.py): streaming Dataset → per-record bundles     │
│ (sorted/paged per-table scans) — the export & preview driver                  │
└──────────────┬────────────────────────────────────────────────────────────────┘
               ▼
┌──────────────────────── STORAGE CORE (existing, extended) ────────────────────┐
│ Dataset.add_records (dataset.py:896, kept)  ·  NEW Dataset.merge_records      │
│ (FK-ordered multi-table upsert, Arrow-accepting)  ·  integrity.py (kept +     │
│ vectorized variants)  ·  table_names.py families (extended §11)  ·            │
│ DatasetInfo slots + spec_version (§11)                                        │
└───────────────────────────────────────────────────────────────────────────────┘
  Orthogonal: io/jobs.py — durable SQLite job+plan store at
  <data_dir>/.pixano/jobs.sqlite (WAL), polled by GUI, shared with CLI.
```

### 3.1 New/changed modules (all paths under `src/pixano/`)

| Module | Key symbols | Contract |
|---|---|---|
| `datasets/io/__init__.py` | `import_dataset()`, `analyze()`, `export_dataset()`, `FORMATS` | The one shared core called by CLI, REST, and Python API. |
| `datasets/io/spec.py` | `ImportSpec`, `ExportSpec`, `SchemaSpec`, `MediaPolicy`, `IdPolicy` | Declarative job description (YAML/JSON/GUI form/flags), Pydantic; `SchemaSpec.compile() → DatasetInfo` normalizes the hand-authorable dialect into the existing manifest form (§4). |
| `datasets/io/registry.py` | `DataFormat`, `Capabilities`, `FormatRegistry` (`FORMATS`) | Static built-ins + `entry_points(group="pixano.formats")`. `params_model.model_json_schema()` powers GUI forms and CLI flags. |
| `datasets/io/importer.py` | `DatasetImporter(ABC)`: `probe(source) → DetectResult\|None`; `analyze(source, spec, limits) → ImportPlan`; `iter_batches(plan, cursor) → Iterator[BatchBundle]`; class attrs `format_name`, `importer_version` (semver), `supports_resume`, `deterministic_ids` | The only surface a format author implements. `analyze` is side-effect-free and uses the same parser as ingest. Iteration order must be deterministic (sorted globs) — a documented invariant. |
| `datasets/io/engine.py` | `ImportEngine.run(importer, plan, spec, sinks) → ImportResult`; `ImportEngine.resume(job_id, sinks)` | Owns everything operational (§8). Fresh builds use `table.add` inside staging; add-mode and resume boundaries use `merge_records`. |
| `datasets/io/ids.py` | `stable_id(ns, *parts) → str`, `IdLedger` | `blake2b-128 → base62`, formatted `"{ns8}-{hash}"` where `ns8` derives from `IdPolicy.namespace` (default: source identity — hub repo id / source dir name — **not** the config hash, so option tweaks don't change identity). Namespace prefix enables manifest-free rollback deletes. `IdLedger` carries id/FK sets across flushes (spills to SQLite past a threshold). |
| `datasets/io/plan.py` | `ImportPlan`, `PreflightReport`, `Finding{code, severity, count, samples+Provenance, suggestion}`, `Provenance{file, line, json_pointer, record_key}`, `SamplePreview` | Fully JSON-serializable; consumed verbatim by the CLI printer and GUI preview; generalizes today's `MetadataValidationReport` UX (`cli/data.py:124-148`). Plans persist in the job store with a `plan_id` + source fingerprint. |
| `datasets/io/errors.py` | `PixanoDataError` hierarchy (`FormatDetectionError`, `SpecValidationError`, `MetadataError`, `MediaResolutionError`, `PlanMismatchError`, …) | Every error is typed and carries `Provenance`. |
| `datasets/io/media.py` | `MediaResolver`, `probe_image`, `probe_video` (per-file probe cache) | Implements the two storage modes (§6). Threaded probing; ffprobe results cached per distinct file (LeRobot shards probed once, not per episode). |
| `datasets/io/manifest.py` | `ImportManifest` | Add-mode journal written **before** the first write: spec + plan fingerprints, id namespace, per-table pre-import Lance versions, importer semver. No id enumeration (the namespace prefix suffices). |
| `datasets/io/progress.py` | `ProgressEvent{phase, done, total?, unit, table_counts, message}`, `ProgressSink`, `TqdmSink`, `JobSink` | One event stream; CLI tqdm with real totals from the plan; throttled job-store writes for the GUI (polling, no SSE in 0.8.0). |
| `datasets/io/jobs.py` | `JobStore` (SQLite, WAL, `<data_dir>/.pixano/jobs.sqlite`), `JobRecord`, `JobRunner` | Durable jobs + persisted plans; states `pending/running/interrupted/done/error/cancelled/rolled_back`; heartbeat; restart marks running jobs `interrupted` (resumable). Local filesystem only — typed rejection for S3 data dirs. |
| `datasets/io/reader.py` | `RecordBundleReader.iter_bundles(dataset, splits?, limit?)` | Streaming export/preview source: one sorted/paged scan per component table batched by `record_id IN (page)` after index creation — never per-record queries. |
| `datasets/io/formats/pixano_jsonl/{spec,parser,importer,exporter,sidecars}.py` | `PixanoJsonlImporter/Exporter`, line models, sidecar decoders | JSONL v2 (§5), including media-only folders (replaces the GUI's `unlabeled_images/videos` path — no separate `media_folder` format). |
| `datasets/io/formats/coco/{importer,exporter}.py` | `CocoImporter`, `CocoExporter`, `CocoParams` | Two-pass streaming (§7.2); exporter fixed (categories populated, keypoints) and round-trip-tested. |
| `datasets/io/formats/lerobot/{importer,layout_v21,layout_v3,hub}.py` | `LeRobotImporter`, `LeRobotParams(revision, episodes, media, frames)` | v2.1 + v3.0, local + hub, Arrow-path metadata, video time-windows (§7.3). No `lerobot` dependency — pyarrow + `huggingface_hub` only. |
| `datasets/dataset.py` (extended) | `Dataset.merge_records(data, check_integrity)`; `Dataset.invalidate_caches(dataset_id)` classmethod hook; scalar-index helpers | `merge_records` = FK-ordered multi-table `merge_insert("id")` upsert accepting rows or Arrow batches — the storage-core primitive that add-mode and resume require (today the only `merge_insert` is inside `update_data`, `dataset.py:1120`, guarded and unusable for bulk). |
| `datasets/exporters/dataset_exporter.py` (refactored in place) | `DatasetExporter` keeps `initialize_export_data/export_record/save_data`; driver rewritten on `RecordBundleReader` + `ProgressSink` + registry binding | Same authoring contract, scalable driver (kills the O(records × tables) scans at `:87-106` and the full `to_arrow()` at `:130`). |
| `api/routers/data_io.py` | `/io/*` routers (§9) | Replaces `api/routers/import_datasets.py` (in-memory `_jobs` dict `:53`, hardcoded `IMPORT_TYPES` `:58`, discarded preflight report `:127-129`, malformed `logger.info` `:85` all go). Deprecated alias `POST /datasets/import` kept one release. |
| `api/routers/views.py` (extended) | `videos` resource routes (list/get/blob with HTTP Range + time-window awareness, `/preview` poster) | §9/§11. Embedded video bytes are served through the blob route with Range support; `http(s)` URIs stay verbatim as today (`views.py:118-122`). |
| `cli/data.py` (rewritten) | `import`, `export`, `jobs`, `formats`, `migrate-jsonl` | §8/§9. `cli/_schema_loader.py` retained solely behind `--importer` / `--info-py` escape hatches (CLI/Python only). |

**Deliberate refusals** (endorsed by all three design critiques): no per-sample IR — the existing `dict[table → rows]` yield shape is already the correct multi-table generalization; it is formalized as `BatchBundle`, not replaced. No Celery/task queue. No SSE/WebSocket — durable job records polled at 2 s, the UI's existing pattern. No Lance blob-encoding in 0.8.0 (spike scheduled — §14.3). No `pixano data convert` (0.8.x; the registry makes it nearly free later). No HF `imagefolder` shim (0.8.x). No browser upload.

## 4. The declarative ImportSpec (replaces `--info file.py:attr`)

`ImportSpec` (`datasets/io/spec.py`): one Pydantic model built identically from a YAML/JSON file (`dataset.yaml`, auto-discovered at the source root), CLI flags, a GUI form (rendered from `model_json_schema()` served by `GET /io/formats`), or Python kwargs.

```yaml
# dataset.yaml
pixano: 2
dataset:
  name: "FLIR ADAS"
  description: "RGB + thermal detection"
  workspace: image                  # UI hint; supplies the preset schema, overridable below
format: pixano_jsonl                # pixano_jsonl | coco | lerobot | auto (detection, §7)
media:
  mode: embed                       # embed (default) | uri            (§6)
schema:                             # optional — analyze() infers and the plan shows it for confirmation
  views:
    rgb: {kind: image}
    thermal: {kind: image}
  record:
    attrs: {license: str}
  entity:
    attrs: {category: str, is_difficult: {type: bool, default: false}}
  annotations: [bbox, multi_path]   # slots to enable; dict form adds fields: {bbox: {attrs: {quality: float}}}
defaults:
  source: {type: ground_truth, name: flir_adas_v2}
ids:
  policy: derive                    # derive | explicit (require `id` per line)
  namespace: flir_adas_v2           # id-prefix identity; defaults to source dir name / hub repo id
mode: create                        # create | overwrite | add
options: {}                         # format params, validated by the format's params_model
```

**Zero new schema language at the storage layer; one thin authoring dialect on top.** `SchemaSpec.compile()` normalizes the hand-authorable shorthand above into the exact `{"base", "fields", "name"}` manifest form that `dataset_schema._serialize_table_schema` / `_deserialize_table_schema` already round-trip through `info.json` — synthesizing a subclass `name` whenever `attrs` are present (the deserializer *silently drops* `fields` on nameless payloads today, `dataset_schema.py:289-291`; that silent drop becomes a hard error) and filling the `required`/`collection` keys `_deserialize_field` demands (`:217-218`). Field types are bounded by `_MANIFEST_TYPES` (`dataset_schema.py:31`) — that boundary **is** the declarative/custom-Python frontier and is documented as such (`dict`-typed custom fields are out of scope for the declarative path).

When `schema:` is omitted, `analyze()` infers it from a bounded scan and embeds the inferred spec in the `ImportPlan` for confirmation — **inference happens once, explicitly, at plan time; never silently at ingest time.**

Workspace presets (the current builders' `DEFAULT_INFO`s, e.g. `folders/image.py:82-93`) become **data** in `io/spec.py`: `workspace: image` pre-fills views/slots exactly as the builders do today, minus the Python.

**Escape hatches** (CLI/Python only; the REST API refuses both — Goal 2): `--info-py file.py:attr` (a `DatasetInfo`, current mechanics via `cli/_schema_loader.py`) and `--importer file.py:Class` (a `DatasetImporter` subclass).

## 5. Pixano JSONL v2 — the normative annotation format

**Principles.** One JSON object per line = one record. **Strict, closed vocabulary**: unknown top-level keys, unknown annotation kinds, and undeclared views are errors with `file:line:json-pointer` provenance and did-you-mean suggestions. **No aliases, no shape inference** — the declared schema drives parsing (a bare-string view value is *schema-resolved*: declared `Image` ⇒ URI; never shape-guessed). One parser (`json.loads` per line) shared by analyze and ingest — killing the preflight-vs-build divergence. **Kind payload keys are exactly the canonical schema field names** (`coords`, `format`, `is_normalized`, `confidence`, `rle.size/counts`, `template_id/coords/states`, `mention/spans_start/spans_end`, …) — the format is self-documenting against the schema reference and needs no renaming layer.

**File layout.** `source/<split>/metadata.jsonl` (split = folder name) or any `*.jsonl` whose lines carry `"split"`. Relative media paths resolve against **the metadata file's directory only** (the dual-root leniency of `folder_base_builder.py:338-356` is dropped). Optional `dataset.yaml` at the source root is the import spec (§4).

**Media-only mode** (replaces the GUI unlabeled path — still no separate `media_folder` format). A source with **no `metadata.jsonl` anywhere** imports raw media directly: images (`.jpg/.png/…`), videos (`.mp4/.mov/…`), or text files (`.txt/.md`), one record per file — or per **stem** when views live in subfolders (`source/<view>/a.jpg` + declared or inferred `schema.views` stem-match into multi-view records; missing stems are warnings). Split folders (`train/val/test` names) may wrap either shape. Layout discovery is deterministic and shared by analyze/ingest; ambiguous layouts (mixed media kinds in one folder, split names mixed with view folders) are **errors, never guesses**. Videos default to **frame extraction** (`SequenceFrame` rows, annotatable, capped by `options.max_frames_per_video`) with `options: {frames: reference}` opting into browse-scale `Video` rows — mirroring the LeRobot importer's contract. Inside a source that *does* carry `metadata.jsonl` splits, a metadata-less split keeps the original constraint (single declared image view).

**Optional header (line 1)** — file-scoped defaults so hand-authored lines stay terse without inference:

```json
{"$pixano": "jsonl/2", "defaults": {"bbox": {"format": "xywh", "is_normalized": true}, "source": {"type": "ground_truth", "name": "import"}}}
```

**Line grammar** (all other top-level keys rejected):

```
id?             string   — else derived: stable_id(ns, split, file_stem, line_ordinal)
split?          string   — else folder name
attrs?          object   — custom Record fields (declared in schema; never implicit top-level spill)
views           {logical_name: ViewValue}
entities?       [Entity]
conversations?  [Conversation]
annotation_files? [Sidecar]
```

`ViewValue` (discriminated by the *declared* view kind):

- **Image**: `"path.jpg"` or `{"uri": "...", "width"?, "height"?}` — `uri` may be a relative path (embed mode only), `http(s)://...`, or `s3://...` (§6)
- **Video**: `{"uri": "clip.mp4", "fps"?, "from_timestamp"?: 0.0, "to_timestamp"?: -1.0}` — a **time window inside the media file** (§11.1); missing technical fields (`num_frames/width/height/format/duration`) are ffprobed once per distinct file (probe cache); `num_frames`/`duration` describe the *window*
- **SequenceFrame**: `{"frames": [{"uri", "frame_index"?, "timestamp"?}, ...]}` or `{"frame_pattern": "frames/bear/*.jpg", "fps": 24}` (lexicographic order — documented determinism invariant)
- **Text**: `{"uri": "doc.txt"}` **or** `{"content": "inline text"}` — two explicit keys (structurally kills the MEL doc-vs-code contradiction)
- **PointCloud**: `{"uri": "sweeps/0001.pcd"}` · **CamCalibration**: reserved for 0.9 (3D deferral; the grammar slot is documented so 0.9 can add it without a format break)

`Entity` = `{"id"?, "parent_id"?, "attrs"?: {...}, "annotations"?: [Ann], "tracklets"?: [{"id"?, "view", "start_timestep", "end_timestep", "start_timestamp"?, "end_timestamp"?}], "states"?: [{"frame_index", "attrs": {...}}]}`. Tracklets are auto-derived per (entity, view) from per-frame annotations when omitted. `states` map to `EntityDynamicState` rows with `entity_id/tracklet_id/view_id` derived and `frame_id` = the matching frame-view row id for SequenceFrame views, or the `""` sentinel for real `Video` views (frame addressing via `frame_index`; the sentinel is skipped by FK checks, `utils/integrity.py:131,227`).

`Ann` = flat list, discriminated on `"kind"`; common keys `view?` (required iff >1 view), `id?`, `frame_index?`, `source?`, plus per-kind fields named after the schema:

| kind | payload (schema-field names) |
|---|---|
| `bbox` | `coords: [4]`, `format: "xywh"\|"xyxy"`, `is_normalized: bool`, `confidence?` — `format`/`is_normalized` required unless supplied by header defaults (defined defaulting, never [0,1]-sniffing) |
| `mask` | `rle: {size: [h,w], counts: str}` **or** `polygons: [[x,y,...], ...]` (hand-authorable; converted to RLE at ingest) |
| `keypoints` | `template_id`, `coords: [2N]`, `states: [N] ∈ {visible,invisible,hidden}` |
| `multi_path` | `coords`, `num_points`, `closed` (mirrors `MultiPath`) |
| `text_span` | `mention`, `spans_start: [int]`, `spans_end: [int]` |
| `classification` | `labels: [str]`, `confidences?: [float]` |
| `relation` | reserved kind; schema-field payload |
| `bbox3d` / `keypoints3d` | reserved for 0.9 (3D deferral) |

`Conversation` = `{"id"?, "messages": [{"type": "SYSTEM"\|"QUESTION"\|"ANSWER", "content", "question_type"? (required for QUESTION, ∈ Message.QUESTION_TYPES), "choices"?, "user"?, "views"?: [logical_name]}]}`. Derivations are defined, not inferred: `conversation_id = stable_id(record_id, "conv", ordinal)`; `number` = 0-based index of the question turn (an ANSWER takes its question's number; SYSTEM takes 0); `user` defaults from header defaults (else `"import"`); `entity_ids = []`.

`Sidecar` (record-level, strictly typed — keeps long-video files hand-authorable and streamable instead of megabyte single lines):

- `{"kind": "mask", "view": "...", "pattern": "masks/bear/*.png", "encoding": "index_png", "entity_map": {"1": "bear_1"} | "auto"}` — indexed PNGs decoded **once** per file and split by pixel value (pixel value → entity key)
- `{"kind": "bbox", "view": "...", "pattern": "bboxes/vid0/*.json", "encoding": "track_json"}` — per-frame files with the now-normative shape `{"view_name"?, "objects": [{"track_id", "bbox", "category", ...}]}` (stem-matched to frames; `track_id` stitches tracklets)

**Determinism & round-trip.** Absent ids derive as: record `stable_id(ns, split, file_stem, line_no)`; view `stable_id(record_id, "view", logical_name, frame_index?)`; entity `stable_id(record_id, "ent", ordinal)`; annotation `stable_id(entity_id, kind, ordinal)`. The `pixano_jsonl` **exporter emits exactly this grammar** (ids included, plus a `dataset.yaml` with the compiled schema), so import → export → import is id-equal — the CI round-trip test. Re-running the same source is a no-op under `add` mode (upsert on equal ids); *editing* a file shifts derived line-ordinal ids by design — users needing edit-stable identity author explicit `id`s (documented).

**Example lines** (each one physical line; wrapped here for readability; these become committed test fixtures):

```jsonl
{"$pixano":"jsonl/2","defaults":{"bbox":{"format":"xywh","is_normalized":true},"source":{"type":"ground_truth","name":"voc2007"}}}
```
```jsonl
{"id":"voc_000042","attrs":{"license":"voc2007"},"views":{"image":"JPEGImages/000042.jpg"},"entities":[{"attrs":{"category":"dog","is_difficult":false},"annotations":[{"kind":"bbox","coords":[0.132,0.28,0.41,0.55]},{"kind":"keypoints","template_id":"animal_pose","coords":[0.5,0.5,0.7,0.5,0.6,0.6,0.6,0.8],"states":["visible","visible","hidden","visible"]},{"kind":"mask","polygons":[[0.13,0.28,0.54,0.28,0.54,0.83,0.13,0.83]]}]}]}
```
```jsonl
{"views":{"rgb":"rgb/000001.jpg","thermal":"thermal/000001.jpg"},"entities":[{"attrs":{"category":"person"},"annotations":[{"kind":"bbox","view":"thermal","coords":[0.41,0.30,0.05,0.12]},{"kind":"multi_path","view":"rgb","coords":[0.10,0.90,0.45,0.62,0.80,0.88],"num_points":[3],"closed":false}]}]}
```
```jsonl
{"id":"seq_bear","views":{"camera":{"uri":"videos/bear.mp4","fps":24}},"entities":[{"id":"bear_1","attrs":{"category":"bear"},"tracklets":[{"id":"t1","view":"camera","start_timestep":0,"end_timestep":81}],"states":[{"frame_index":40,"attrs":{"occluded":true}}],"annotations":[{"kind":"bbox","view":"camera","frame_index":0,"coords":[0.10,0.20,0.30,0.40]},{"kind":"bbox","view":"camera","frame_index":12,"coords":[0.12,0.21,0.30,0.40]}]}]}
```
```jsonl
{"views":{"camera":{"frame_pattern":"frames/bear/*.jpg","fps":24}},"annotation_files":[{"kind":"mask","view":"camera","pattern":"masks/bear/*.png","encoding":"index_png","entity_map":"auto"}]}
```
```jsonl
{"views":{"image":"000001.jpg"},"conversations":[{"messages":[{"type":"QUESTION","content":"What is the greatest number? <view:image>","question_type":"SINGLE_CHOICE","choices":["0","15","3.14","58"]},{"type":"ANSWER","content":"58"}]}]}
```
```jsonl
{"views":{"image":"images/eiffel.jpg","text":{"content":"The Eiffel Tower is a wrought-iron lattice tower in Paris."}},"entities":[{"attrs":{"name":"Eiffel Tower"},"annotations":[{"kind":"bbox","view":"image","coords":[0.3,0.1,0.4,0.8]},{"kind":"text_span","view":"text","mention":"Eiffel Tower","spans_start":[4],"spans_end":[16]}]}]}
```
```jsonl
{"id":"ep_000017","attrs":{"episode_index":17,"tasks":["pick the red block"],"length":412},"views":{"cam_top":{"uri":"https://huggingface.co/datasets/acme/pickplace/resolve/v3.0/videos/observation.images.top/chunk-000/file-000.mp4","fps":30,"from_timestamp":68.27,"to_timestamp":82.0},"cam_wrist":{"uri":"https://huggingface.co/datasets/acme/pickplace/resolve/v3.0/videos/observation.images.wrist/chunk-000/file-000.mp4","fps":30,"from_timestamp":68.27,"to_timestamp":82.0}}}
```

The last line is exactly what the LeRobot importer materializes internally for a hub-hosted dataset (uri mode) and what the JSONL v2 exporter writes for window-addressed video views — export output *is* valid import input by construction.

## 6. Media storage contract

**Two modes only. Embed is the default.** (Product decision: embedding raw data in LanceDB is the optimal path — the tables are built for it and no files need to be saved or managed on the server; URI mode covers large-scale data already resident in a datalake. Pixano never copies, stages, relocates, or serves local files; there is no media-root concept anywhere in the design.)

- **`media.mode: embed` (default).** Views store `raw_bytes`; blob columns are already promoted to `pa.large_binary()` at table creation (`dataset.py:206-213`). Local/relative file paths in metadata are valid **only** in embed mode: the engine reads each file exactly once at ingest, under byte-bounded buffering (§8). Serving stays the existing DB-blob pattern (`GET .../{view}/{id}/blob` — `views.py:82-96`); the new videos route adds **HTTP Range** support over embedded bytes so `<video>` seeking works. Consequences, documented rather than hidden: import cost is proportional to media size; Lance copy-on-write maintenance (compaction) is likewise proportional — the Lance blob-encoding storage-class spike (§14.3) is the scheduled optimization for this default.
- **`media.mode: uri`** — for data already in a datalake. Rows store the URI verbatim; the browser fetches it directly, exactly as `_image_src` does today (`views.py:118-122`). `http(s)://` is fully supported (this includes HF-hub `resolve/` URLs and presigned S3 URLs). Raw `s3://` URIs are accepted at import with a plan `Finding` stating that browser viewing requires user-side serving (presigned URLs or a gateway). **Bare local filesystem paths are a validation error in uri mode** — they are not fetchable by a browser; the error message points to embed mode. This closes the arbitrary-file-read hazard that a "serve whatever path is in the row" endpoint would create.
- `DatasetInfo.storage_mode` (`filesystem`/`embedded`/`mixed`, `dataset_info.py:100`) is finally **honored by import** instead of force-set (`folder_base_builder.py:127` today); mixed datasets (e.g. embedded images + uri videos) are legal and recorded as `mixed`.
- Existing embedded datasets require no migration — the read path is already mode-aware (`get_view_binary`, `dataset.py:547`).

Per-format defaults: `pixano_jsonl` and `coco` → embed (uri opt-in; COCO `coco_url` honored in uri mode); `lerobot` → policy per source (§7.3).

## 7. Format registry & built-in formats

```python
# datasets/io/registry.py
@dataclass(frozen=True)
class Capabilities:
    media_kinds: frozenset[str]          # {"image","video","sequence_frames","text","point_cloud"}
    annotation_kinds: frozenset[str]     # {"bbox","mask","keypoints","multi_path","message","text_span",...}
    source_kinds: frozenset[str]         # {"local_dir","local_file","hf_hub"}
    supports_resume: bool
    deterministic_ids: bool

@dataclass(frozen=True)
class DataFormat:
    name: str                                    # "pixano_jsonl" | "coco" | "lerobot"
    title: str
    importer_cls: type[DatasetImporter] | None   # None ⇒ export-only
    exporter_cls: type[DatasetExporter] | None   # None ⇒ import-only
    params_model: type[BaseModel]                # → GUI JSON-Schema form + CLI --opt flags
    capabilities: Capabilities
    detect: Callable[[SourceRef], DetectResult]  # cheap sniff → (confidence, evidence)

FORMATS = FormatRegistry(builtin=[PIXANO_JSONL, COCO, LEROBOT])
# third parties: [project.entry-points."pixano.formats"] my_fmt = "pkg.mod:MY_FORMAT"
```

One record gives import/export symmetry (FiftyOne's best pattern minus the class-tree explosion and dotted-string resolution), the GUI picker with capability-based greying (COCO export disabled for VQA datasets), and a nearly-free `convert` in 0.8.x. **Auto-detection** (`--format auto`, GUI default): `meta/info.json` with `codebase_version` ⇒ lerobot; a JSON with `images`+`annotations`+`categories` keys ⇒ coco; `dataset.yaml`, a `$pixano` header, or v2 `metadata.jsonl` ⇒ pixano_jsonl. Ties/no-match ⇒ `FormatDetectionError` listing candidates — never a guess.

### 7.1 `pixano_jsonl`

Importer + exporter for §5, including media-only folders (subsumes the GUI's `unlabeled_images/videos` types). `analyze` streams every line through the single strict parser; ingest reuses the good parts of today's `factories.py`/`processors.py` (message construction, indexed-PNG→RLE, `track_id` stitching) as pure helpers with the heuristics stripped. Exporter writes the identical grammar (round-trip test).

### 7.2 `coco`

Importer: **two-pass streaming** (the COCO `annotations` array is *not* grouped by `image_id`, so single-pass grouping would require unbounded buffering): pass 1 streams `annotations` via `ijson` into an on-disk SQLite spill keyed by `image_id` (also yielding exact totals); pass 2 streams `images` joining the spill; resume cursor = image ordinal. Small files (below a configurable threshold) take an in-memory fallback; `ijson` is an optional extra with a documented size warning without it. Detection / segmentation (polygon + RLE → `CompressedRLE`) / keypoints (COCO-17 template registered); categories → `entity.category` strings (no int freezing — taxonomies stay mutable in an annotation store). Media: `file_name` read and embedded (default) or `coco_url` honored as an http reference in uri mode. Exporter: `coco_dataset_exporter.py` logic moved onto the new driver — `categories` actually populated (empty today, `coco_dataset_exporter.py:88`), keypoints added, `pixano_*` id extensions kept ⇒ exact round-trip.

### 7.3 `lerobot`

v2.1 + v3.0, local dir or hub (`huggingface_hub.snapshot_download` of `meta/**` only, tag-pinned revision; **no `lerobot` dependency** — both layouts parsed with pyarrow directly, per the audit's version-drift warning).

**Mapping:** episode → record (`attrs`: `episode_index`, `tasks`, `length`, per-episode stats, plus `data_uri`/`data_from_index`/`data_to_index` referencing the frame parquet — **frame rows are never exploded**: DROID-scale sets have 10⁷–10⁸ frames × dozens of features); each `dtype: video` camera → one `Video` view row with the episode's time window (`from_timestamp`/`to_timestamp` from the episodes parquet for v3; the whole file for v2.1); technical fields from `features[key]["info"]` (no probing). `image`-dtype cameras are not exploded either: default = record-level parquet reference + a `Finding` explaining that frame browsing needs opt-in extraction (`frames: extract`, capped by `max_frames_per_episode`, size-estimated in the plan).

**Media policy (per §6):**

| Source | Mode | Mechanics |
|---|---|---|
| Local directory | `embed` (default) | Per-episode clip extraction — `ffmpeg -ss {from} -to {to} -c copy` (stream copy; cheap and frame-safe at LeRobot's GOP=2) — then the clip bytes are embedded on the `Video` row with a degenerate window (`from_timestamp=0`). The plan shows a total-size estimate before ingest; `episodes:`/`max_*` params allow partial import. The source dataset is never modified. |
| HF hub, public repo | `uri` | View `uri` = `https://huggingface.co/datasets/{repo}/resolve/{tag}/{path}` (browser-fetchable); window fields address the episode inside the shard mp4. Meta files only are downloaded. |
| HF hub, private/gated | choice surfaced as a plan `Finding` | Either `embed` (snapshot the shards, extract + embed clips) or provide a user-served gateway URL prefix for uri mode. |
| Datalake mirror (http/S3) | `uri` | `uri_prefix` param rewrites shard paths onto the user's serving endpoint; window fields as above. |

Episode metadata flows through the **Arrow path** (`pa.RecordBatch` per table). `analyze` ffprobes one shard per camera and emits a codec `Finding` (LeRobot v3 defaults to AV1/`libsvtav1` — unplayable in Safari/older Chrome; documented limitation, no transcoding in 0.8.0).

### 7.4 Custom Python builders

Subclass `DatasetImporter`, yield `BatchBundle`s; run via the Python API, `--importer file.py:Class`, or ship as an entry-point plugin (which also makes the format appear in the GUI picker — installed code, never uploaded code). The legacy `DatasetBuilder` (`builders/dataset_builder.py`) is **kept working untouched and deprecated for one release** — no adapter is built (an adapter cannot make `shortuuid`-id builders resumable or idempotent anyway); its docs point at the new ABC. A `DatasetImporterTestCase` harness (TFDS dummy-data style) runs a real importer end-to-end into a temp dataset and asserts per-table row counts.

## 8. Execution pipeline

**Phase 1 — analyze (pure, bounded).** `analyze(source, spec?, limits) → ImportPlan`. Streams metadata with the same parser as ingest; validates strictly; resolves/probes media (sampled, capped); infers schema if unspecified; counts records/media per split for progress totals; collects `Finding`s (typed code + severity + count + samples with `Provenance` + suggestion — a strict generalization of today's preflight report, whose CLI rendering at `cli/data.py:124-148` is kept); captures N normalized preview records (metadata + at most K local thumbnails — **no remote video decoding, no unbounded line-counting**: API analyze reads the first N MB/lines by default and flags totals as estimates; CLI `--dry-run` may do the full scan). The plan carries `plan_fingerprint = hash(spec_fingerprint, source_fingerprint)` and is persisted in the job store with a `plan_id`.

**Phase 2 — plan confirmation.** CLI prints the plan (format, splits, counts/estimates, schema, findings, media-size/codec warnings) and asks to proceed (`--yes` skips; `--dry-run` stops). GUI renders the same JSON as the wizard's preview step. Ingest executes a *plan*: `POST /io/imports {plan_id}` or `{spec}` (which re-analyzes); if the source fingerprint changed since analysis ⇒ `PlanMismatchError`.

**Phase 3 — ingest.** `ImportEngine.run()`:

- **Batching.** Per-table buffers flushed at `max(rows=1024, bytes=256MB)` thresholds (byte-aware — embedded media inflates rows; with embed as the default this is the primary memory guard). Importers yield either Pydantic rows (ergonomic path — pixano_jsonl) or per-table `pa.RecordBatch`es (Arrow path — LeRobot metadata, COCO floods). Insert order stays `Dataset._INSERT_ORDER` (`dataset.py:871-878`).
- **Integrity at scale.** The engine's `IdLedger` carries id and FK state **across flushes** (today `add_records` re-initializes `known_ids` per call, `dataset.py:945`, and `validate_batch` never checks the DB for id uniqueness, `integrity.py:209-217` — cross-flush duplicates are silently written; the ledger closes this hole). On fresh create/overwrite builds, DB lookups are skipped entirely (nothing pre-exists) — eliminating the per-flush `find_ids_in_table` scans (`dataset.py:754-773`). Arrow batches get vectorized invariants (`pyarrow.compute`: non-empty ids, `is_in` FK checks against the ledger, cheap value checks), plus the first batch per table is round-tripped through Pydantic as a validation canary; each importer's trust boundary is declared in its `DataFormat`.
- **Atomicity.** `create`/`overwrite` build in `<data_dir>/.pixano/staging/{name}-{job_id}/` and atomically rename into `library/{name}` (overwrite: journal → rename old to `<data_dir>/.pixano/trash/` → rename staging in → delete trash; the journal is replayed on server boot so a crash between renames is recoverable). Staging and trash live **outside** `library/` — `DatasetInfo.load_directory`'s `glob("*/info.json")` (`dataset_info.py:319,380`) would otherwise list trashed copies; the glob additionally learns to skip dot-directories as defense in depth. Finalize calls `Dataset.invalidate_caches(dataset_id)` — clearing the API's eternal `_dataset_cache` (`api/routers/_deps.py:18-45`) and `_num_rows_cache` — and retries the directory swap on Windows (open handles). `add` mode writes the `ImportManifest` **before** the first write and routes every flush through `Dataset.merge_records` (upsert on `id`), so re-running a completed add cannot duplicate.
- **Indexes.** At finalize (and before add-mode merge phases) the engine creates BTree scalar indexes on `id` and `record_id` for every table — no index exists anywhere today, so `merge_insert`, FK lookups, export paging, and the UI's `record_id = 'x'` browses are all full scans at present. This also speeds the app generally.
- **Rollback (add mode).** `DELETE /io/jobs/{id}` / `pixano data jobs rollback`: if every table's current Lance version still equals the manifest's post-import version (no concurrent writes), restore pre-import versions; otherwise delete by id-namespace prefix (`id LIKE '{ns8}-%'`) — which cannot touch rows written by the GUI or other imports. Version-restore is never applied over concurrent writes (the data-loss footgun is structurally closed); no dataset-wide write lease is needed for add-mode ingest.
- **Resume.** After each committed flush the engine persists `{cursor (importer-opaque, e.g. {"split":"train","line":40960} or {"episode_ordinal":1234}), per-table counts}` to the job store. `resume` re-enters `iter_batches(plan, cursor)`; the redelivered boundary batch goes through `merge_records`, so at-least-once delivery + deterministic ids = exactly-once effect. Importers with `deterministic_ids=False` (e.g. custom `shortuuid` builders) are **non-resumable by declaration**: restart-only, always into fresh staging.
- **Progress.** `ProgressEvent`s with plan totals → `TqdmSink` (CLI ETA) and `JobSink` (throttled ≥0.5 s job-store writes; GUI polls — no SSE in 0.8.0).
- **Finalize.** Stats, dataset preview, video poster extraction (`ffmpeg` at `from_timestamp`, stored in `preview` bytes), scalar indexes, provenance stamp `{dataset}/imports/{job_id}.json` (spec, fingerprints, importer semver, per-table counts — TFDS-style reproducibility), job → `done`.

## 9. Job model, REST API, CLI, GUI wizard

**Job model** (`io/jobs.py`). SQLite (WAL) at `<data_dir>/.pixano/jobs.sqlite`: `jobs(id, kind[import|export], dataset, status, spec_json, plan_id, progress_json, cursor_json, manifest_path, error_json, pid, heartbeat, created_at, updated_at)` + `plans(id, plan_json, source_fingerprint, expires_at)`. Single in-process worker (concurrency 1) with cooperative cancellation checked at flush boundaries; server restart marks running jobs `interrupted` (resumable); the CLI runs jobs in-process and records them in the same store, so the GUI sees CLI imports. S3 `data_dir`/`library_dir` (`api/settings.py:47-48`) ⇒ typed `UnsupportedStorageError` for all io jobs in 0.8.0 (the guard currently at `import_datasets.py:224` is preserved in the new router, not dropped).

**REST API** (`src/pixano/api/routers/data_io.py` + `views.py` extensions):

```
GET    /io/formats                    # registry + params JSON Schema → GUI forms
POST   /io/analyze                    # {source, format?, spec?, limits?} → ImportPlan (+plan_id)
POST   /io/imports                    # {plan_id} | {spec, source, mode} → 202 {job_id}
POST   /io/exports                    # {dataset_id, format, destination, media, options} → 202 {job_id}
GET    /io/jobs        /io/jobs/{id}  # list / poll (status + progress + report)
POST   /io/jobs/{id}/cancel  /resume
DELETE /io/jobs/{id}                  # add-mode rollback via manifest
GET    /datasets/{id}/videos[...]     # list/get + /blob (HTTP Range over embedded bytes, window-aware) + /preview
POST   /datasets/import               # deprecated alias, one release
```

**CLI** (`src/pixano/cli/data.py` rewritten):

```
pixano data import  DATA_DIR SOURCE [--format auto] [--spec dataset.yaml] [--mode create|overwrite|add]
                    [--media embed|uri] [--dry-run] [--yes] [--max-records N] [--resume JOB_ID]
                    [--importer file.py:Class] [--info-py file.py:attr]      # advanced escapes
pixano data export  DATA_DIR DATASET DEST --format pixano_jsonl|coco [--media files|uris]
pixano data jobs    [list | show | cancel | resume | rollback] [JOB_ID]
pixano data formats
pixano data migrate-jsonl SRC [DST]     # best-effort v1 metadata.jsonl → v2 converter (frozen after 0.8.0)
```

**GUI wizard** (extends the existing `ImportDatasetModal.svelte` + `lib/api/datasets.ts`, keeping the existing 2 s polling pattern): format picker (from `/io/formats`, capability-greyed) → source path/URI + params form (JSON-Schema-rendered) → analyze → preview step rendering the full `ImportPlan` (findings with samples, inferred schema for confirmation, counts, media-size estimate) → confirm → polled progress with percentages → done/error with the full report. This replaces the current flow that discards the validation report (`import_datasets.py:127-129`).

## 10. Export symmetry

The refactored `DatasetExporter` driver streams `RecordBundleReader` bundles (per-table paged scans over the new `record_id` index — never per-record queries), keeps the 3-method authoring contract, reports through `ProgressSink`, and runs as a job. Export media policy: `files` (dump embedded bytes to relative paths next to the JSONL — required for round-tripping embedded datasets) or `uris` (write stored URIs verbatim; error with guidance if the dataset is embedded-only). Round-trip tests in CI: `pixano_jsonl` (id-equal) and COCO (semantic-equal with `pixano_*` extensions). `default_jsonl_dataset_exporter.py` is superseded by the `pixano_jsonl` exporter (export format == import format at last); `default_json_dataset_exporter.py` is kept as a debug dump.

## 11. Data-model changes

1. **Video time-window** (`src/pixano/schemas/views/video.py`): add `from_timestamp: float = 0.0`, `to_timestamp: float = -1.0` (−1 ⇒ end of media). A `Video` row = *a time window inside the media at `uri` (or in the embedded bytes)*; whole files are the degenerate window; `num_frames`/`duration` describe the window. Frame addressing: `media_ts = from_timestamp + frame_index / fps`; `PerFrameAnnotation.frame_index`/`EntityDynamicState.frame_index` are window-relative; `frame_id` uses the `""` sentinel (no frame rows exist for real videos). Naming is `from_timestamp`/`to_timestamp` **everywhere** (JSONL, schema, API — matches LeRobot's own episode metadata). Migration: although the folder video branch is dead code, users *can* have declared `Video` via `--info` + custom builders — so `Dataset.__init__` performs a one-time `add_columns` backfill (defaults) on `videos` tables missing the columns, stamped via the new `DatasetInfo.spec_version` (§11.6); reads and writes both survive (the exact-field-set write guards at `dataset.py:842-844`/`:1082-1084` would otherwise break the first post-upgrade write).
2. **Close the orphan-schema gap (2D half)** (`src/pixano/schemas/table_names.py` + `dataset_info.py`): add canonical families `("classification","classifications","classifications",ANNOTATION,Classification)` and `("relation","relations","relations",ANNOTATION,Relation)`; matching typed slots in `_DATASET_INFO_SLOT_TYPES` (`dataset_info.py:53-64`) and `supported_dataset_info_slots()` (`table_names.py:75-93`). **This is not free plumbing** — `RESOURCE_ROUTERS` is a hand-maintained tuple, so the per-family REST resource stubs + API models are explicitly budgeted (P0/P4). *Deferred to 0.9 (3D deferral):* the `bbox3d`/`keypoints3d`/`cam_calibration` families, the `renderable: bool` flag on `CanonicalResourceFamily`, and the non-renderable exclusion in `_resolve_fk_target_tables`'s `frame_id` targets (`integrity.py:46-47`) — these ship together with the separate 3D workstream.
3. **CamCalibration↔camera binding** — *deferred to 0.9 in full (3D deferral)*: the planned design (`target_logical_name: str = ""` naming the calibrated camera view — a shared-`logical_name` scheme is unimplementable since `DatasetInfo.views` is a dict keyed by logical name — plus removing the bogus "must be positive" validators on `Extrinsics`/`Intrinsics`) is recorded here so the 3D branch can adopt it; 0.8.0 does not touch `camcalibration.py`.
4. **Workspace enum reconciliation** — *deferred to 0.9 (3D deferral)*: the backend `WorkspaceType.PCL_3D = "3d"` matching the UI's existing `PCL_3D = "3d"` (`ui/apps/pixano/src/lib/types/dataset.ts:41`) lands with the 3D workstream.
5. **Storage-core primitives**: new `Dataset.merge_records()` (FK-ordered multi-table `merge_insert("id")` upsert, rows or Arrow batches) — required by add-mode idempotency, resume, and rollback; scalar-index creation helpers; `Dataset.invalidate_caches()` hook.
6. **`DatasetInfo.spec_version: int = 2`** (absent ⇒ 1): enables the `add_columns` migration above and future evolutions; existing datasets load unchanged (all schema changes are additive with defaults).
7. **Consistency fixes riding along**: `add_records` stamps `created_at/updated_at` like `add_data` does (`dataset.py:855-859` vs `:964-967`); `DatasetFeaturesValues` gains the `records`/dynamic-state bridges so `add_constraint` stops raising `AttributeError` (`dataset.py:1239` area); the `"record"` docstring at `dataset.py:96` corrected to `"records"`.
8. **Explicitly deferred**: Lance blob-encoding storage class for `raw_bytes` (§14.3); a first-class sensor-series table for LeRobot state/action curves (parquet references until the UI can plot them).

## 12. Existing code: kept / refactored / deleted — and migration

**Kept (unchanged or extended):** `Dataset.add_records` + `_INSERT_ORDER` + `utils/integrity.py` (extended with `merge_records`, vectorized variants, ledger-aware entry points) · `schemas/table_names.py` canonical-family registry (extended §11.2) · `DatasetInfo` slots/views model + diff serialization (with the nameless-payload silent drop turned into an error) · `TableQueryBuilder`, `ViewFamilyIntegrityValidator`, `create_instance_of_schema` · `DatasetBuilder` (untouched, deprecated one release, no adapter) · `DatasetExporter`'s 3-method authoring contract and its tests · the preflight-report CLI rendering UX, re-targeted at `PreflightReport`.

**Refactored:** exporter driver (in place, on `RecordBundleReader`) · `coco_dataset_exporter.py` → `io/formats/coco/exporter.py` (categories fixed, keypoints, round-trip-tested) · `default_jsonl_dataset_exporter.py` superseded by `io/formats/pixano_jsonl/exporter.py` · `builders/folders/metadata.py` streaming-validation core → `io/formats/pixano_jsonl/parser.py` (alias map, shape inference, case-insensitive matching, `pa_json` build parser all deleted) · `factories.py` message/entity construction and `processors.py` PNG-index/track-stitching → pure helpers under `io/formats/pixano_jsonl/` with heuristics stripped · workspace `DEFAULT_INFO`s → data presets in `io/spec.py` · `cli/data.py` rewritten on `ImportSpec` (`cli/_schema_loader.py` kept only behind escape hatches; `_snake_case_name` deduplicated into `utils`) · `api/routers/import_datasets.py` → `api/routers/data_io.py` · `api/routers/views.py` extended (videos routes) · UI `ImportDatasetModal.svelte` + `lib/api/datasets.ts` → wizard (§9).

**Deleted (clean break):** `FolderBaseBuilder` and the four workspace builders (`folders/{folder_base_builder,image,video,vqa,mel}.py`) once `pixano_jsonl` reaches parity — including `metadata_alias_map`/`resolve_schema_key_from_value` inference (`metadata.py:161-212`), the dual-parser divergence (`folder_base_builder.py:785`), the dead `is_video` uri branch, forced `storage_mode="embedded"` (`:127`), and `mosaic.py`'s write-into-the-user's-source behavior (multi-image single views become a v2 validation error: declare multiple views or a sequence) · `_builder_path_for_workspace`, `--use-image-name-as-id`, `--info` as the front door · the in-memory `_jobs` dict + daemon-thread import path + hardcoded `_ImageEntity` schemas + the discarded-report behavior · `workspaces/dataset_items.py` legacy helpers and the `DatasetItem` stubs · the stale `docs/tutorials/dataset.md` · the contradictory MEL doc examples · all v1 alias/inference tests (replaced by v2 strict + round-trip + engine tests).

**Migration & compatibility:**
- Already-imported datasets stay readable with no migration (additive schema changes only, gated by `spec_version`).
- `pixano data migrate-jsonl` converts v1 `metadata.jsonl` (including alias spellings) to v2 best-effort, emitting a report of lines needing manual attention; frozen after 0.8.0.
- v1 files fed to the v2 importer fail with errors that point at `migrate-jsonl`.
- `POST /datasets/import` remains as a deprecated alias for one release; `DatasetBuilder` is deprecated for one release.
- The pixano-cookbook recipes are rewritten against v2 with **zero Python** for the standard cases (the current recipes require a `DatasetInfo` `.py` plus an 80–380-line converter each).

## 13. Phased implementation plan

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0 — schema & storage groundwork** | §11 items 1–7 minus the 3D deferrals: classification/relation families + slots + resource-router stubs, `Video` window + `add_columns` migration + `spec_version`, `merge_records`, scalar-index helpers, cache-invalidation hook, timestamp/features-values fixes. No blob encoding, no 3D. | Existing datasets open unchanged; new slots round-trip `info.json`; `merge_records` upsert test (run twice ⇒ identical row counts); indexes measurably accelerate `find_ids_in_table`. |
| **P1 — io core** | `io/{spec,registry,importer,engine,ids,plan,errors,media,progress,manifest}.py`; atomic create/overwrite with staging/trash/journal outside `library/`; `IdLedger`; deterministic ids; tqdm progress; Python API `analyze()`/`import_dataset()`. | A toy importer runs end-to-end: analyze → confirm → atomic build; kill −9 mid-create leaves the library byte-identical; derived-id collision detection fires in analyze. |
| **P2 — JSONL v2 + CLI** | `formats/pixano_jsonl` importer+exporter (incl. sidecars, media-only mode); `SchemaSpec` normalization (+ serializer silent-drop fix); format auto-detect; new `pixano data import/export/formats` CLI; `migrate-jsonl`; `DatasetImporterTestCase` harness; normative format spec page in docs-astro; cookbook recipes rewritten with zero Python. | Golden round-trip (import→export→import id-equal) for image/multi-view/video-track/VQA/text-span fixtures — the §5 example lines are committed fixtures; v1 files fail with migration-pointing errors. |
| **P3 — COCO + LeRobot + scale** | `formats/coco` (two-pass streaming, det/seg/kpts, exporter round-trip); `formats/lerobot` (v2.1+v3, local+hub, Arrow path, window views, clip-extraction embed path, codec Finding); videos REST routes + Range + posters; `RecordBundleReader` + rewritten export driver; memory-ceiling test (source ≫ RAM under byte-bounded buffering). | COCO round-trip on a real subset; a hub v3 dataset imports meta-only in bounded memory (uri mode); a local v3 subset imports via clip-extraction embed within its plan size estimate; a 1M-record synthetic dataset imports and exports within linear-time budgets. |
| **P4 — jobs + API + GUI** | `io/jobs.py`; `api/routers/data_io.py` (+ deprecated alias); GUI wizard (format picker → analyze preview with findings/samples → confirm → polled progress); **video browse MVP**: record list with poster thumbnails + `<video>` playback of the episode window via the Range-enabled blob route — explicitly *without* frame-accurate annotation overlay (full player = 0.8.x, own workstream). | GUI imports a COCO folder with visible preflight report and percentage progress; jobs survive server restart as `interrupted`; a LeRobot episode's window plays in the browse view (H.264 sets; AV1 documented). |
| **P5 — resume, rollback, hardening, docs** | Flush-boundary checkpoints + `--resume`; add-mode manifest + `DELETE /io/jobs/{id}` rollback (version-match guard, else namespace-delete); cancel; S3 typed rejections; Windows swap retry; docs (spec reference, importer-author guide, migration guide, AV1/media-mode limitations). | kill −9 mid-LeRobot-import → `resume` completes with zero duplicates; rollback of an add leaves concurrent GUI edits intact; `uv run pytest` green incl. revived CLI e2e on new fixtures. |

## 14. Accepted trade-offs & advisory notes

1. **Media: embed-default, uri for datalakes — strict rule, no local serving** (product decision). Local sources embed; datalake sources use fetchable URIs. Consequences accepted openly: (a) importing a local multi-TB LeRobot dataset in embed mode copies clip bytes into LanceDB — the plan surfaces a size estimate first, and partial import (`episodes:`) plus hub/datalake uri mode are the scale paths; (b) import cost and Lance compaction cost are proportional to embedded media size; (c) raw `s3://` URIs are not browser-viewable without user-side serving (plan Finding). The rejected alternative (a Pixano endpoint serving registered local directories) would have added a server file-serving surface the product explicitly does not want.
2. **Clean break on JSONL v1** — alias/inference deleted, not deprecated; one-shot `migrate-jsonl` provided. One-time churn (the cookbook has already survived one rewrite) buys a single normative grammar and one parser.
3. **Lance blob-encoding deferred but prioritized.** Embedded media currently lives in `large_binary` columns; `TableQueryBuilder` already excludes blob columns from default projections (`queries/table.py:213-217`), so scans are protected, but compaction/rewrite costs remain proportional to media size. Because embed is now the **default**, the 0.8.x spike (verify Lance blob storage class + `take_blobs` against the pinned `lancedb >= 0.29.0, < 0.30.0` — `pyproject.toml:33` — including `merge_insert` interaction, and budget the `get_view_binary`/preview/temporal-batch reader rewrite) is the top post-0.8.0 storage priority, shipped as an opt-in migration with a dual read path.
4. **Strictness over magic at ingest; magic only at analyze** — schema/format inference exists but is always surfaced in the plan for confirmation, never silently applied.
5. **Two importer yield paths** (Pydantic rows / Arrow batches) with asymmetric validation strength — mitigated by vectorized invariants + first-batch canary + declared trust boundaries. Forcing one path either caps LeRobot/COCO throughput or makes hand-written importers hostile.
6. **Resume granularity = flush boundary** with merge-upsert on the boundary batch; importers without deterministic ids are restart-only. Exact row journaling isn't worth its complexity.
7. **Add-mode atomicity is manifest + guarded version-restore/namespace-delete, not a transaction** — LanceDB has no cross-table transactions; convergent recovery via deterministic ids is the right weight. Version-restore never fires over concurrent writes.
8. **Id namespacing derives from source identity, not the config hash** — re-running with tweaked options stays idempotent; two *genuinely different* sources given the same namespace can collide (documented; analyze detects).
9. **Line-ordinal derived ids** — re-running the same file is idempotent; *editing* the file shifts identities. Users needing edit-stable ids author explicit `id`s.
10. **Polling, threads, file/SQLite jobs — no queue, no SSE** — restart-survivability and resume solve the actual failure mode of a local-first tool; the job schema is queue-ready if scale-out ever matters.
11. **LeRobot frame tables stay as parquet references** (state/action *and* image-dtype frames) — exploding 10⁷–10⁸ rows into an annotation store is cost without benefit until the UI can plot/browse them; opt-in capped extraction covers the browse case.
12. **Video window denormalized onto `Video` rows** (in uri mode the shard uri repeats across episodes) — simpler than a media-file table; acceptable at episode counts.
13. **CamCalibration modeled as a non-renderable view family with `target_logical_name`** — semantically it's sensor metadata; a new schema group isn't worth the churn. *(Deferred to 0.9 with the rest of the 3D scope.)*
14. **0.8.0 video is "browse + play the window," not "annotate on video"** — the frame-accurate player (requestVideoFrameCallback + Konva sync + frame_index-keyed state) is its own 0.8.x workstream; AV1 playback limits are documented, not transcoded away.
15. **S3 libraries rejected for io jobs** — staging/rename, manifests, and SQLite are POSIX-shaped; object-store-safe write patterns are a later, deliberate project.

### 14.1 Release numbering

This work was planned as 0.7.3 and is renumbered **0.8.0** (product-owner confirmed): it removes a shipped metadata dialect and the `--info` CLI, which a patch number would misrepresent. `migrate-jsonl` and the one-release deprecated API alias soften the break.

## 15. Open questions

1. **Lance blob storage class** (§14.3): does the pinned lancedb release expose `take_blobs` through the `Table` wrapper, and how does blob encoding interact with `merge_insert` and compaction? (0.8.x spike.)
2. **S3-native libraries**: which write patterns (staging, manifests, job store) get object-store-safe equivalents, and when?
3. **Merge-by-key annotation re-import** (import labels onto existing records): requires a stable `media_key` on views that also works for embedded datasets — design in 0.8.x.
4. **AV1 policy**: document-only (current), or offer opt-in transcode-at-import for Safari support?
5. **Sensor-series data** (LeRobot state/action curves): first-class table + UI plotting, or keep parquet references permanently?
6. **Upload path**: if browser upload is ever wanted (no server-visible path), what staging story fits the no-server-files constraint?
