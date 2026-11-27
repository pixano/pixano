# REST API

**Status:** Draft
**Owner:** @vmulet-benzo
**Last agreed change:** 2026-11-26
**Covers:** `src/pixano/api/`, except `src/pixano/api/jobs/`, `src/pixano/api/routers/jobs.py` (`JOB`), `src/pixano/api/routers/data_io.py` (`IO`) and `src/pixano/api/routers/inference.py` (`INF`)

## Purpose and concepts

The REST API is the HTTP surface of `pixano-api`. Today that is the app that `pixano server run` starts. The legacy app, the new UI, the command line and any other client read and write datasets through it.

This spec covers every route of the app but three groups: the jobs routes (`/jobs`) belong to `JOB`, the import and export routes (`/io`, and the deprecated `/datasets/import`) to `IO`, and the inference routes (`/inference`) to `INF`. It covers the routes that describe the datasets, read and write their rows, read their views and media, review a model's annotations, list and filter the records, give the overview, the statistics, the embedding spaces and the semantic search, and tell the health of the app. It also covers how the app answers on every route: its errors, its pages, its compression, the cross-origin requests and the pages of the interface. [The routes today](#the-routes-today) lists the whole surface. What the rows hold, and the values `review_status` takes, belong to [`data-model.md`](./data-model.md) (`DATA`).

This spec obeys every rule of [`architecture.md`](./architecture.md) ([ARCH-1](./architecture.md#between-the-specs)). Several of those rules are targets for the API. This spec describes the code as it is, and decides nothing against them:

- **The catalogue of datasets** ([ARCH-5](./architecture.md#control-plane), [DATA-32](./data-model.md#storage-roots-platform-and-catalogue), targets). The app finds a dataset by scanning the library's folders for the `info.json` that holds the id. `Dataset.find`, behind the dataset-scoped routes, `GET /datasets/{id}`, `/stats` and `/datasets/info/{id}/splits`, reads the folder named after the id first; `DatasetInfo.load_id`, behind `GET /datasets/{id}/info` and the bookmark, does not. `GET /datasets` lists the folders in the order of their names, and skips one whose `info.json` it cannot read. The other routes skip none, and answer 500 when their scan meets it (API-1).
- **Authentication** ([ARCH-35](./architecture.md#security) to ARCH-37). No route authenticates its caller. The media routes are plain URLs, used in an `<img>` element and by `fetch`.
- **Versioned routes, and no dependence on the interface or on the server's machine** ([ARCH-54](./architecture.md#repository-packages-and-frontend)). No route carries a version. `GET /datasets/{id}` answers the paths of the dataset on the server (`path`, `previews_path`, `thumbnail`), which both interfaces copy and never use, and the 404 of `GET /datasets/{id}/info` names the library's folder. The routes mix two styles: `/datasets/{id}/info` and `/datasets/{id}/stats`, but `/datasets/info/{id}/splits` and `/datasets/info/{id}/bookmark`.
- **A cache of media and summaries** ([ARCH-19](./architecture.md#media-cache-and-the-way-to-the-inference)). Only the preview routes send `Cache-Control: public, max-age=3600` and an `ETag`. The blob routes and the frame batch send neither, no route answers `304` to `If-None-Match`, and a preview of a given size is made again at each request. The app has three caches, each in one process and with no bound: the datasets it holds (`_dataset_cache`, `src/pixano/api/routers/_deps.py`); the values of `split` and `status` that the explorer lists, one entry per version of the records table, never emptied (`_enum_cache`, `src/pixano/api/query.py`); and the values of the entities' attributes offered to compose a statistic (`_values_cache`, `src/pixano/datasets/statistic_choices.py`). Several reads take whole tables, or whole columns, at each request ([DATA-48](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene), target): the overview, the health of the embeddings, the neighbors of a record (`Dataset.get_neighbors`), the review queue (`src/pixano/api/review.py`), the values of `split` and `status` once per version of the records table, and a page of records sorted or filtered on a computed column (`src/pixano/datasets/queries/computed_columns.py`).
- **A change reaches every replica** ([ARCH-20](./architecture.md#media-cache-and-the-way-to-the-inference)). The end of a job of the queue reaches every replica that receives its event (API-3), and a rewritten `info.json` or `embeddings.json` is seen on a local dataset (API-2). A row that one process writes, such as a person's save of an annotation, or vectors added to a space without a change of `embeddings.json`, is not seen by another process that holds the dataset, which reads its tables at the version it opened them, until it opens the dataset again or writes to it (API-3, API-88).
- **No shared state in one process** ([ARCH-8](./architecture.md#control-plane)) and **heavy work as jobs of the queue** ([ARCH-23](./architecture.md#execution-plane)). Each process holds its datasets, and one registry of statistics per library, whose lock serialises additions in that process only. `POST /datasets/{id}/embeddings/compute` runs in a thread of the app, recorded in the SQLite store of the import jobs (which [ARCH-5](./architecture.md#control-plane), target, keeps jobs out of) and polled at `GET /io/jobs/{id}` (`IO`). Because of that store, it answers 400 when the library is on S3, or is not the folder `library` of a data directory. What that thread does is today's behaviour, not a rule (`src/pixano/api/embeddings.py`). It embeds one image per record, the first row of `images`. Without `force`, it skips the records the model already holds a vector of, so that starting it again resumes it. With `force`, it empties that model's space only, keeping its id, its place and the default, or deletes every model's embeddings when `embeddings.json` could not be read completely. It writes the vectors to the space of the checkpoint that the inference tells after each call, and fails when the inference cannot be asked. The embeddings job of the worker, where ARCH-23 moves this work, does otherwise: it embeds each medium, skips nothing, and falls back on the checkpoint told at planning (`JOB`, `packages/pixano-worker/src/pixano_worker/kinds/embeddings.py`).
- **Write leases** ([ARCH-14](./architecture.md#data-plane)). A write holds a file lock beside a local dataset, and nothing on S3 (API-34). Once it holds the lock, each write method of the dataset rewrites the dataset's mutation marker (`.pixano-mutation`), which tells the import engine that the dataset changed, before the dataset's own integrity check (`dataset_write`, `src/pixano/datasets/locking.py`). So a write that this check refuses, and a `DELETE` of a row that does not exist, rewrite the marker too. The checks of the service (references, review rules, `id_conflict`) come before it, and a write they refuse leaves the marker as it was, except when resolving the resource first created a missing table (API-21), which rewrites it too. [DATA-33](./data-model.md#storage-roots-platform-and-catalogue) (target) replaces the marker.
- **Reads that write nothing** ([ARCH-15](./architecture.md#data-plane), [DATA-42](./data-model.md#concurrency-write-leases-and-read-only-open)). A request on an annotation or entity resource whose table is missing creates it, a `GET` included (API-21). `GET /datasets`, `GET /datasets/{id}/info` and the bookmark write the dataset's mosaic, `previews/dataset_preview.jpg`, when it is missing. Opening a dataset of an older layout migrates it, and `GET /datasets`, `/datasets/{id}/info`, the bookmark, `/datasets/info/{id}/splits` and the description that `GET /datasets/{id}` answers each open the dataset again.
- **A caller's filter never pasted into SQL** ([ARCH-40](./architecture.md#security), [DATA-47](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene)). The equality filters of the resource lists (`record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`) are pasted between quotes without escaping (`BaseService.list`, `src/pixano/api/service.py`), and so are those of the view lists (`src/pixano/api/routers/views.py`) and of the conversations. So a value that holds a quote changes the query: `record_id=a'b` answers 500, `record_id=x' OR '1'='1` matches every row, and the equality of API-20 does not hold for such a value (see its _Today:_ line). Escaping the values would make API-20 hold for them, but would not by itself follow ARCH-40: an escaped value is still pasted into a SQL string, and ARCH-40's _Today:_ line counts `to_sql_list`, which escapes, among the filters pasted. How a filter is validated or passed as a parameter is for ARCH-40 and DATA-47 to say. Every one of these lists also takes a raw clause, `where`, pasted as it is, and answers 500 to a malformed one, where the records list answers 400. The explorer's filters are compiled from a grammar, against the columns it lists, and their values quoted (`src/pixano/api/query.py`), but the records list, the neighbors, the overview and the search still take the explorer's raw clause.
- **Size limits on bodies** ([ARCH-39](./architecture.md#security)). No body of this part is bounded, and nor is the `k` of a search. What is bounded: `limit` (API-6), the explorer's filters and free text (API-60), and a statistic's label and description (API-65).
- **The inference cannot be reached** ([ARCH-59](./architecture.md#inference-plane)). The readiness never fails on it (API-91). A text search and the embeddings computation need a provider, and answer 404 `No inference provider connected` without one.
- **One frontend** ([ARCH-53](./architecture.md#repository-packages-and-frontend)). `/` serves the legacy app. It serves the new UI only when `ACTIVATE_UI_V1_0` is true and the browser sends the cookie `pixano_ui_version=next`, so a cookie left by an earlier deployment cannot reach it once the setting is off. `GET /app/ui` tells the legacy app whether to show its button that switches to the new UI. Both go with the switch that ARCH-53 removes.
- **Timestamps** ([DATA-10](./data-model.md#schemas-types-timestamps-and-serialization), target). The view routes answer `created_at` and `updated_at` as Python prints a date (`2026-11-26 10:00:00.123456`), and the other routes in ISO 8601 (`2026-11-26T10:00:00.123456`). Neither carries a time zone: rows are stamped with the server's local time, with none.

At startup, the app replays the imports that a stopped process left half done, and marks their jobs interrupted. That belongs to `IO`. Playing a video by HTTP Range, read from the `videos` table, is [DATA-23](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media) (target), and no route does it: there is no `/videos` route.

The words this spec uses:

- A **dataset-scoped route** is a route under `/datasets/{dataset_id}/`.
- A **resource** is one kind of row a client reads, and for most kinds writes, through the generic routes: a record, an entity, an entity dynamic state, one kind of annotation, the time series or the embeddings. Each is declared once, as a `ResourceSpec` (`src/pixano/api/resources.py`).
- The **service** is `BaseService` (`src/pixano/api/service.py`): the checks and writes that every resource shares.
- A **view route** reads the views of a dataset and their bytes (`src/pixano/api/routers/views.py`). Views are written by an import only.
- A **page** is the answer of a list route: `{items, total, limit, offset}`.
- A **model's row** is an annotation whose `source_type` is `model`. A **person's row** is any other.
- A **decision** is a review status a person asks for on a model's row. There is one: `accepted`.
- An **echo** is a status a request sends back without asking for anything: the status the row already holds, or `pending`.
- The **content** of an annotation is every field but its provenance (`source_type`, `source_name`, `source_metadata`), its score fields, its `review_status` and the server's timestamps.
- A **reviewable kind** is an entity annotation that an interface can review: every entity annotation but tracklets, relations and text spans (`pixano.schemas.is_reviewable_annotation`). A **reviewable view** is a view that an interface can show for review: a still image, a point cloud or a text, and not a video, a frame of a sequence or a PDF (`pixano.schemas.is_reviewable_view`).
- The **write lock** of a dataset is what keeps other writes out while one write request checks and writes. Today it is a file lock beside a local dataset (`dataset_mutation_lock`), and there is none on S3. [ARCH-14](./architecture.md#data-plane) and [DATA-39](./data-model.md#concurrency-write-leases-and-read-only-open) (targets) replace it with a write lease.
- A **busy dataset** is a dataset whose write lock another writer holds.
- A **computed column** is a column of the records that a job computed in a table of its own: a statistic per record, `record_statistics.<name>`.
- The **explorer's request** is what a client sends to list records: its filters (`filter`, `col:op:value` tokens), its free text (`q`), its sort (`sort`, `order`) and a raw clause (`where`). The raw clause is deprecated and kept for older clients.
- An **embedding space** is one model's vectors, at one checkpoint, in a table of their own ([DATA-43](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene)).

## Rules

### Every route

**API-1 (target).** Every dataset-scoped route, `GET /datasets/{id}`, and every route under `/datasets/info/{id}/` MUST answer 404 when the library holds no dataset of that id, with the detail `Dataset '<id>' not found.`

_Why:_ a client tells a dataset deleted, or never there, from a fault of the server by this answer. How the app finds a dataset today is in the bullet on the catalogue of datasets.

_Today:_ in a library that holds an `info.json` this build cannot read, a request whose scan meets that file before its dataset answers 500, and so does every request for an unknown id: neither `Dataset.find` (`src/pixano/datasets/dataset.py`) nor `DatasetInfo.load_id` (`src/pixano/datasets/dataset_info.py`) skips the file. And the 404 of `GET /datasets/{id}/info` names the library's folder instead (see the bullet on ARCH-54).

**API-2.** On a local dataset, once another process has rewritten its `info.json` or `embeddings.json`, or replaced its folder, the next request MUST be served with the dataset's current schema.

_Why:_ a job of the worker gives the entities a new field, or adds a mask table or an embedding space, while the app holds the dataset. Read with the schema it held, the app would leave them out. Today the app checks these files before each request, and opens the dataset again when one changed. A dataset on S3 is never checked, and keeps the schema it was first read with until the app drops it (API-3). [ARCH-20](./architecture.md#media-cache-and-the-way-to-the-inference) (target) carries a change to every replica, whatever the storage.

**API-3.** When `PIXANO_DATABASE_URL` is set, every read of the app MUST see the rows that a job of the queue wrote once this process has received the job's terminal state event.

_Why:_ the end of a job is when an interface reloads a record to show what the job wrote. Until then, today, a process may serve a table at the version it holds: the job's last state event drops the dataset the app holds, on every replica that listens to the job events (`JOB`, [ARCH-9](./architecture.md#control-plane)). So a client can read a job done in PostgreSQL before this process has received the event. And an event lost while the listener reconnects is never replayed to that drop, which leaves the table at its old version (`src/pixano/api/jobs/events.py`). [ARCH-20](./architecture.md#media-cache-and-the-way-to-the-inference) (target) carries every change to every replica.

**API-4.** An error that a route raises MUST be answered as JSON `{"detail": D}`. D is a sentence; or, with the status 422, the list of the request's validation errors; or, for a coded error, an object that carries `code` and `message`. The coded errors today are `dataset_busy` and `dataset_replaced` (409, API-34) and `id_conflict` (409, API-24). An exception that no route catches is answered 500 in plain text.

_Why:_ clients read the server's words for a failure from these three shapes, and read the code of a 409 to tell a write they can retry from a write refused.

**API-5.** A request whose path, query or body does not match the types and bounds the route declares MUST be answered 422. A request that matches them, but that the dataset's schema, its references or the review rules refuse, MUST be answered 400.

_Why:_ both store nothing (API-33), and the split tells a malformed request from one the data refuses. The legacy save queue keeps the person's edit staged on both.

**API-6.** Every route that answers a page (the resource lists, the records list, the view lists and the conversations) MUST take `limit`, from 1 to 1000 (default 100), and `offset`, from 0 to 2^63-1 (default 0), and MUST answer 422 outside these bounds. It MUST answer `{items, total, limit, offset}`, where `total` counts every row the request matches, and `limit` is the size applied.

_Why:_ clients page until they hold `total` rows, stepping by the `limit` the server answered.

**API-7.** The media routes (`/blob`, `/preview` and `/sframes/batch`) and the event streams MUST NOT be compressed. Other answers of 500 bytes or more are compressed with gzip when the client accepts it.

_Why:_ media are compressed already. And gzip buffers: a compressed stream reaches the browser only when it ends.

**API-8.** The app MUST send the headers that allow a cross-origin request only to the origins that `CORS_ORIGINS` lists, and MUST NOT allow credentials on them. With no origin listed, it sends no such header.

_Why:_ the app is same-origin in development, through the Vite proxy, and in production, where it serves the interface. A client of another origin authenticates with no cookie ([ARCH-54](./architecture.md#repository-packages-and-frontend), target). These headers only tell a browser whether a page of another origin may read an answer. They keep no request out: a simple request from another page still reaches the app and runs, a `GET` that creates a missing table included (API-21), and nothing checks the `Host` header. Keeping callers out belongs to authentication ([ARCH-35](./architecture.md#security), target), and to reads that write nothing ([ARCH-15](./architecture.md#data-plane), target).

**API-9.** In the app that `pixano server run` starts, a `GET` on a path that no route serves MUST be answered 404 in JSON when the path is under a prefix of the API (`/datasets`, `/io`, `/jobs`, `/inference`, `/statistics`, `/health`, `/app`), a static mount (`/_app`, `/_legacy_app`, `/app_models`) or the docs (`/docs`, `/redoc`, `/openapi.json`). Any other path MUST be redirected (307) to the hash route of the legacy app, `/#/<path>?<query>`.

_Why:_ an API client gets a JSON 404, never an HTML page, and a deep link of the legacy app, which routes by hash, still opens.

### The datasets

**API-10.** `GET /datasets` MUST list every dataset of the library that its caller may see, in a stable order, and MUST skip a dataset it cannot describe rather than fail. It MUST answer `[]` when the library holds no dataset.

_Why:_ one broken dataset must not hide the library. Today it answers `[]` too when the library cannot be found, a folder that does not exist read as empty (`DatasetInfo.load_directory`), so a mistyped `LIBRARY_DIR` shows an empty library. [DATA-30](./data-model.md#storage-roots-platform-and-catalogue) (target) makes a missing or unreachable storage root fail fast with a typed error instead. What a caller may see belongs to the rights of [ARCH-35](./architecture.md#security) (target), which this spec does not decide. Today no route authenticates its caller, so every caller sees every dataset, with its name, its count and its mosaic.

**API-11.** The routes that describe a dataset MUST leave the statistics tables out: `GET /datasets` and `GET /datasets/{id}/info` carry no table, `GET /datasets/{id}` lists none of them, and `GET /datasets/{id}/stats` counts none of them.

_Why:_ no interface reads rows of them as it reads a view or an annotation. What a dataset computed is answered apart, by `GET /datasets/{id}/statistics`.

**API-12.** `GET /datasets/{id}` MUST answer `tables` as `{table name: schema class name}`, without the tables of the embedding spaces that `embeddings.json` names, beside `info`, the dataset's description, whose schema slots and views are serialized schemas.

_Why:_ both interfaces build their schema of the dataset from `tables` and the slots of `info`. A search reads an embedding space through `embeddings.json`, and its table bears no schema that a client could tell from a view's.

**API-13.** `GET /datasets/{id}/stats` MUST answer `{group: {table: row count}}` for every group of tables but the records and the statistics, the embeddings included. It MUST leave out an empty group, and MUST count 0 for a table it cannot count.

_Why:_ the legacy library card shows the number of view tables, the entities and the annotations of each table. A count that fails must not hide the others.

**API-14.** `GET /datasets/info/{id}/splits` MUST answer `[{split, status, count}]`, sorted by split and then by status, and `[]` when the records carry no `status` column or cannot be read.

_Why:_ the legacy library card shows the progress of each split.

**API-15.** `PATCH /datasets/info/{id}/bookmark?bookmark=` MUST add the bookmark when the dataset lacks it, and remove it when the dataset holds it. On a local dataset, it MUST NOT let another write land between its read of the bookmarks and its write (API-34). The bookmark MUST be `TODO`, `NEW` or `FAVORITE`: any other is answered 422. The answer MUST be the dataset's description with its new bookmarks.

_Why:_ the legacy library pins datasets by bookmark, and reads the bookmarks back from the answer. A toggle is not idempotent: a repeated call removes what the first added.

### Resources

**API-16.** Every annotation kind, the entities, the entity dynamic states and the time series MUST get the same routes, status codes and checks, from one declaration of the kind, at `/datasets/{dataset_id}/{path}` and `/datasets/{dataset_id}/{path}/{id}`. The records have a router of their own (`src/pixano/api/routers/records.py`), which adds the explorer's list and writes through the same service (API-19). The views are read through the view routes (API-48 to API-53), and the conversations through a read-only route built on the messages.

_Why:_ one mechanism serves every kind, so a new kind is declared once and gets the same routes and the same checks as the others. Today the declaration is a `ResourceSpec` (`src/pixano/api/resources.py`), the mechanism is `create_resource_router` (`src/pixano/api/routers/resources.py`), and no such kind has a CRUD router written by hand.

**API-17.** The path of a resource MUST be its resource name in `src/pixano/schemas/table_names.py`: its canonical table name, with `_` written `-`.

_Why:_ both interfaces derive the route of a table from the table's name (`resourcePathForTable`).

**API-18.** The time series MUST be read only: list and get. Every annotation kind, the entities, the entity dynamic states and the records MUST take list, get, create, update and delete.

_Why:_ time series come from an import. A method that a resource does not take is answered 405. What the `embeddings` resource takes is an open question.

**API-19.** Every route of this API that creates, updates or deletes a record, an entity or an annotation MUST write it through the service.

_Why:_ the reference checks, the review rules and the orphan prune live in the service. A write that goes around it skips them. How the worker and an import write belongs to `JOB` and `IO`, and what the rows hold to `DATA`.

**API-20 (target).** A resource list MUST filter by equality on the query parameters that its kind declares, and on no other. The entities take `record_id`. The tracklets, classifications, relations and text spans take `record_id`, `entity_id`, `view_name` and `source_type`. The boxes, 3D boxes, masks, multi-paths, keypoints and entity dynamic states take `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id` and `frame_index`. The messages take `record_id`, `view_name` and `source_type`. On today's `timeseries` layout, one row per frame ([DATA-26](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media), _Today:_), the time series take `record_id`, `view_name` and `frame_index`. `view_name` MUST match a view's `logical_name`, and the `view_id` of any other row.

_Why:_ clients load the rows of one kind for one record, and for one view. Today a kind declares them in `ResourceSpec.list_filters` (`src/pixano/api/resources.py`), which also holds the deprecated raw clause `where`, and holds it by default: a kind declared with the default takes the raw clause. [ARCH-40](./architecture.md#security) (target) removes that clause, so a kind added must not take it ([SPEC-14](./README.md#rules)).

_Today:_ two cases do not follow it. A value that holds a single quote changes the query, because the lists paste the values between quotes without escaping them (see the bullet on ARCH-40). And the messages also declare `entity_id`, which their table does not hold, and answer it 500 (`MESSAGE_RESOURCE`, `src/pixano/api/resources.py`). Escaping the values, and removing that filter, follow this rule (ARCH-40 asks more than escaping: see the bullet on ARCH-40).

**API-21.** A list or get of a view collection, of the time series or of the entity dynamic states whose table the dataset lacks MUST be answered 404 (the frame batch answers 400, API-52). An annotation or entity resource whose table is missing is the exception today: any request on it, a `GET` included, creates the empty table and records it in its family's slot of `info.json`, then goes on, so that a list answers an empty page. The conversation routes do the same for the messages. [ARCH-15](./architecture.md#data-plane) (target) removes that exception.

_Why:_ the legacy workspace loads every collection of a record and treats a 404 as empty. Today the keypoints' slot is not written: the service looks for a slot named after the resource, `keypoints`, where the family's slot is `keypoint` (`BaseService.resolve_table`, `src/pixano/api/service.py`; `src/pixano/schemas/table_names.py`). Their table is created, but once the app reads `info.json` again, it is no longer among the dataset's tables until the next request on the keypoints.

**API-22.** A request body MUST be allowed to carry the fields of the dataset's own schema beyond those of the base kind, and the answer of a row MUST carry them. An entity created without a required field of the dataset's own entity schema of type text, whole number, decimal number, yes-or-no or list MUST get the empty value of that type: `""`, `0`, `0.0`, `false` or `[]`.

_Why:_ a dataset declares its own attributes of an entity, such as a class, and the interfaces create entities with the base fields alone. Today a required field of any other type is not filled, and the create is refused (`_pad_entity_payload`, `src/pixano/api/resources.py`).

**API-23.** An answer MUST leave out every binary column that its schema does not answer as text, such as a view's `raw_bytes` and `preview`. A mask's `counts`, stored as bytes, MUST be answered as its compressed RLE string, so that a client can decode the mask.

_Why:_ rows are JSON. Media bytes have routes of their own (API-50). Today a resource leaves out what is still bytes once its row is serialized (`serialize_row`, `src/pixano/api/models.py`), which a mask's `counts` is not: its schema answers it as text (`CompressedRLE`, `src/pixano/schemas/annotations/compressed_rle.py`). The view routes answer models that hold no bytes. Today the `embeddings` resource answers without its vector (`response_exclude_fields`, `src/pixano/api/resources.py`), and the search reads the vectors on the server: whether that resource serves them is the open question on it.

**API-24.** A create MUST carry the row's id, chosen by the client. A create that repeats an id with the same content, compared after validation and without `created_at` and `updated_at`, MUST answer 201 with the stored row and store nothing. A create that names an id holding other content MUST be answered 409 with `{"code": "id_conflict", "message"}`, and change nothing. On a local dataset, two creates of one id that run at the same time MUST NOT both store their row: the second is answered as above, or 409 `dataset_busy` (API-34).

_Why:_ a client that lost the answer to a create can send it again safely. On S3 no lock keeps two writes apart, and two such creates can both store their row (`BaseService.create`, `src/pixano/api/service.py`).

**API-25.** An update (`PUT`) MUST leave every field that its body does not send as it is stored. An update of an id that the table does not hold MUST be answered 404, and MUST NOT create the row.

_Why:_ clients send only what they edit, without the id, and must not bring back a row deleted meanwhile. Today every field has an empty value other than `null` (`""` for `parent_id`), and a client clears a field by sending it. Today a field sent as `null` keeps its stored value too (`merge_update_payload`, `src/pixano/api/models.py`): what `null` asks for, once [DATA-13](./data-model.md#schemas-types-timestamps-and-serialization) (target) stores absent values as `null`, is the open question on clearing a field.

**API-26.** A create, answered 201, and an update, answered 200, MUST answer the row as it was stored: after the review rules (API-39, API-40 to API-43) and the empty values of API-22, so that its `review_status` is the stored one. The answer to an update of an entity carries the entity alone, and none of the annotations that the edit stored `accepted` (see the open question on an entity's edit): a client reads those back. Every `DELETE` without `only_if_unnamed` that deletes its row MUST answer 204 with no body.

_Why:_ the legacy review shows the status the server stored, read from the answer (`createReviewReflection`, `ui/apps/pixano/src/lib/utils/reviewActions.ts`). An answer that echoed the body would show an edited model's row pending, although the server stored it accepted.

**API-27.** A create or an update that names a record, an entity, a tracklet or an entity dynamic state that does not exist MUST be answered 400. So MUST a create that names one in an entity's `parent_id` or in a message's `entity_ids`. No route checks a `view_id`.

_Why:_ an annotation must not point at a missing entity.

**API-28.** A create of a box, a 3D box, a mask, a multi-path or keypoints that names a tracklet or an entity dynamic state of another entity than its own MUST be answered 400. So MUST a create of an entity dynamic state that names a tracklet of another entity.

_Why:_ a row's tracklet and its entity must agree.

**API-29.** An end of a relation, `subject_id` or `object_id`, that a create or an update through the API fills MUST name an annotation, or be answered 400.

_Why:_ a relation links annotations ([DATA-19](./data-model.md#annotations-provenance-and-review)). Only the Python API, with its integrity check off, stores a relation whose end names an entity, which API-36 still counts. An empty end is not checked: a relation with neither end is stored, with a 201 (`src/pixano/datasets/utils/integrity.py`).

**API-30.** A `PUT` whose body carries an `id` other than the one in its path MUST be answered 400, for every resource, before the rules are checked and before anything is written.

_Why:_ the rules are checked on the row that the path names, and the merged row would be written under the body's id, over another row.

**API-31.** The 404 of a row that does not exist MUST be a sentence that names the row's id between single quotes, `'<id>'`.

_Why:_ the legacy save queue tells a row gone, whose update it drops, from a dataset gone, whose updates it keeps, by finding `'<id>'` in the detail (`ui/apps/pixano/src/lib/api/saveOrchestration.ts`). Today the service answers `Resource '<id>' not found in '<table>'.`, the view routes `Resource '<id>' not found.`, and the blob routes `Resource '<id>' has no embedded blob.`, for a row that does not exist as for a row without bytes.

**API-32.** A `DELETE` of a row that does not exist MUST be answered 404, and MUST delete no row and change no other row.

_Why:_ clients count a 404 on a delete as done already, and must know that nothing else was deleted.

**API-33.** Every check that can refuse a write MUST run before the request writes its first row, so that a 4xx answer means that nothing of the request was stored. The exception is the annotation or entity table, and the slot of `info.json` that records it, that resolving the resource creates when the dataset lacks it (API-21).

_Why:_ a client can then drop or retry a refused write safely. Only a 5xx, a network error or a lost answer leaves it unsure whether the write was stored.

**API-34.** On a local dataset, another write MUST NOT land between a write's checks and the writes that rely on them: a write of the service, a bookmark, a change of the embedding spaces, and the creation of a missing table on any request. A request that meets a busy dataset, and does not get its write lock, MUST be answered 409 with the code `dataset_busy`. A request whose dataset was replaced on disk after the app checked it for this request MUST be answered 409 with the code `dataset_replaced`, and the app opens the dataset again at the next request. Neither wrote anything.

_Why:_ a check means nothing if another write can land before the write that relies on it. The code tells a client that a retry is safe. Today the means is the file lock of a local dataset (`src/pixano/datasets/locking.py`), held across the checks and the writes. A dataset replaced before the request is opened again first, and served (API-2). On S3 there is no lock, and nothing keeps two writes apart: [ARCH-14](./architecture.md#data-plane) and [DATA-39](./data-model.md#concurrency-write-leases-and-read-only-open) (targets) replace the lock with a write lease that holds on both. Today a request does not wait for the lock, and the 409 comes at once. [DATA-41](./data-model.md#concurrency-write-leases-and-read-only-open) (target) gives an interactive save a bounded wait first: a save that gets the lease during it goes on, and the 409 that ends it carries what DATA-41 says (see the open question on a save that meets a write lease).

### Deleting entities

**API-35.** Every entity resource MUST accept `?only_if_unnamed=true` on its `DELETE`. With it, the entity MUST be deleted only when no stored row names it, and the answer MUST be 200 with `{"deleted": true | false}`, or 404 when there is no such entity. On a local dataset, a write that names the entity MUST NOT land between the search for such rows and the delete (API-34).

_Why:_ a client that loads one record at a time cannot see every row that names an entity. Only the server sees every table. On S3 there is no lock, and such a write can land between the search and the delete (`BaseService.delete_if_unnamed`, `src/pixano/api/service.py`). Without `only_if_unnamed`, today, the entity is deleted whatever names it, and the answer is 204: whether such a delete is refused or cascaded is an open question.

**API-36.** A row MUST count as naming an entity when it is an annotation of any table that names it by `entity_id`, by `entity_ids`, or by a relation's `subject_id` or `object_id`; an entity that names it by `parent_id`; or an entity dynamic state that names it by `entity_id`. Each table MUST be asked only about the columns it has.

_Why:_ an entity deleted while one of these rows names it leaves that row pointing at nothing.

**API-37.** An annotation's `DELETE`, and an update that changes an annotation's `entity_id`, MUST accept `?prune_orphan_entity=true`. With it, the entity the annotation named before MUST be deleted once no stored row names it, by the check of API-36. Without it, the entity MUST be left as it is. On a local dataset, a write that names the entity MUST NOT land between that check and the delete (API-34).

_Why:_ the server is the only place that sees every reference, so the prune is one mechanism for every kind, and it does not change a plain delete or update. On S3 there is no lock, and such a write can land between them (`BaseService`, `src/pixano/api/service.py`).

### Review

**API-38.** The review rules MUST be the same for every entity annotation, whatever its kind, including the kinds that no interface reviews yet. Today they live in `src/pixano/api/review.py` and the service. [DATA-17](./data-model.md#annotations-provenance-and-review) (target) moves the consistency of `source_type` and `review_status` into the schema.

_Why:_ one rule set covers every kind, so a new kind needs nothing registered to follow it.

**API-39.** An update that changes the content of a model's row of an entity annotation MUST store it `accepted`, whether it was `pending` or `accepted`. The content MUST be compared after validation, so that a body that changes nothing, or an empty body, accepts nothing.

_Why:_ the person chose to keep that annotation. Left pending, it would be replaced by the next run of the model, which replaces pending rows only.

**API-40.** An update of a model's row, a message included, MUST keep its `source_type`, `source_name` and `source_metadata` whatever the client sent, and keep its scores as [DATA-14](./data-model.md#annotations-provenance-and-review) requires.

_Why:_ the score and the provenance belong to the model. The web interface sends its own source and a score of 1 with every edit, which erased the score of an edited box.

**API-41.** When an update of a model's row changes a field whose scores are aligned with it ([DATA-14](./data-model.md#annotations-provenance-and-review)), a value the person adds MUST take the score the client sent at its position, in a list aligned with the field. A value added without such a score MUST be answered 400.

_Why:_ scores kept as stored while the labels change would score other labels, or no longer match their number and fail validation.

**API-42.** An update of a model's row of an entity annotation MUST take `accepted` as its only decision. It MUST treat `pending`, and the status the row already holds, as echoes that change nothing. It MUST answer 400 to the empty status, unless the row is stored with none (an echo), and to any value other than `pending` and `accepted`. An update MUST NOT take a row back from `accepted`.

_Why:_ a client that edits by sending back every field it read sends the status back too, and `pending` is a status that no person gives.

**API-43.** A person's row MUST take no review status: a non-empty `review_status` on a person's row MUST be answered 400, on a create and on an update, except the echo of the status the row already holds. A create of a model's row MUST accept `pending`, `accepted` or no status.

_Why:_ a person's annotation has nothing to review. The legacy smart tracking and interactive segmentation store a model's output with no status.

**API-44.** The API MUST NOT offer a status for a rejection, and a `DELETE` MUST apply no review rule. A person rejects a model's row by deleting it, as [DATA-14](./data-model.md#annotations-provenance-and-review) says.

_Why:_ rejecting deletes the row, so no status is needed to say it.

### The review queue

**API-45.** `GET /datasets/{id}/review/next?status=&after=` MUST answer `{record_id, remaining}`. `record_id` is the first record after `after`, in record id order, that holds a model's annotation at that status, wrapping round to the first record; it is `null` when no record does. `remaining` counts those records, including the one being left while it still holds one. `pending` also finds a model's row stored with no status. `status` MUST be `pending`, the default, or `accepted`; any other value MUST be answered 422.

_Why:_ the server finds the next record whatever the kind, so the review needs one call and no list per kind.

**API-46.** The queue MUST scan only the tables of a reviewable kind. It MUST leave out a row drawn on a view that is not a reviewable view, named by its id or by its logical name, and that row keeps its status. A row with no view, or naming a view the dataset does not hold, MUST stay in the queue.

_Why:_ a row that no interface can review would keep its record in the queue for good, and the record proposed must always show something to review. Today it also skips a table that lacks the `review_status` column, where no decision could be stored: a dataset of an older layout whose migration on open failed, on a read-only library for instance ([DATA-52](./data-model.md#layout-versioning-and-migrations-spec_version), _Today:_). See the open question on a dataset that is not migrated.

**API-47.** `GET /datasets/{id}/review/next` MUST NOT create a table, or a slot in `info.json`, of a dataset.

_Why:_ a review must not change a dataset's tables. Today the queue reads only the tables the dataset already has, and resolves none through the service, which creates a missing annotation table (API-21).

### Views and media

**API-48.** The `src` of an image, a frame or a point cloud that holds no `uri` MUST be the route of its bytes, `/datasets/{dataset_id}/{images|sframes|point-clouds}/{id}/blob`.

_Why:_ a view holds a `uri` or embedded bytes ([DATA-21](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media)), and the browser fetches embedded bytes through the blob route. No route serves a file by its path on the server. There is no `/videos` route ([DATA-23](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media), target). Today the `src` of a view that holds a `uri` is that `uri`, as it is, and the browser fetches it directly. How media held outside the dataset reach a browser is not decided ([ARCH-12](./architecture.md#data-plane), [ARCH-19](./architecture.md#media-cache-and-the-way-to-the-inference), [ARCH-54](./architecture.md#repository-packages-and-frontend), [DATA-22](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media)): see the open question on the media.

**API-49.** On a dataset that holds `calibrated_images` or `images`, but not both, the image routes (`/images`, `/images/{id}`, its `/blob` and `/preview`, and `/records/{record_id}/images`) MUST read that table. They MUST answer one shape, whose calibration fields are `null` for a plain image.

_Why:_ the interfaces treat both families as images under one route. Today, on a dataset that holds both, the routes read `calibrated_images` only, so that calibration is not lost (`_resolve_image_table`, `src/pixano/api/routers/views.py`): the rows of `images` are out of them, and the preview that API-55 gives one of them answers 404. See the open question on the two families.

**API-50.** A blob route MUST answer the row's embedded bytes, with the media type of the row's `format`, or `application/octet-stream` for a format it does not know. It MUST answer 404 when the row holds no embedded bytes.

_Why:_ an `<img>` element or a 3D loader uses the bytes and their media type directly. Today it answers the bytes whole, and no route answers a `Range` request ([ARCH-19](./architecture.md#media-cache-and-the-way-to-the-inference), [DATA-23](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media), targets).

**API-51.** The preview route of an image or a frame MUST take `size` among 128, 256 and 512, and answer 400 to any other. With a size, it MUST answer an image that fits in a square of that side. Without a size, it MUST answer the stored preview. It MUST answer 404 when there is nothing to show. The preview of a point cloud is the image stored at import, and takes no size.

_Why:_ the record cards ask for thumbnails of 256 pixels (API-55). Today a sized preview is a JPEG made at each request from the view's embedded bytes. When the view holds no bytes the route can read, such as a view built from a `uri` by the Python API, the route answers the stored preview instead, as it is, whatever the size asked. It still fits, because the preview Pixano makes is at most 64 pixels (`_generate_preview`, `src/pixano/schemas/views/image.py`). A preview that came with an imported row as it is has no such bound. [DATA-24](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media) (target) keeps explorer grids from reading the full bytes, and [ARCH-19](./architecture.md#media-cache-and-the-way-to-the-inference) (target) serves thumbnails through a cache.

**API-52.** `GET /datasets/{id}/records/{record_id}/sframes/batch` MUST answer `multipart/x-mixed-replace; boundary=frame_boundary`. Each part MUST carry `Content-Type`, `Content-Length` and `X-Frame-Index`, and the parts MUST be in `frame_index` order. It MUST answer 404 when no frame matches, and 400 when the dataset has no table of sequence frames.

_Why:_ the legacy video player streams the frames batch by batch, and parses each part by its `Content-Length`.

**API-53.** With `view_name`, or on a record of one sequence view, the frame batch MUST cover every frame of `[start_frame, start_frame + batch_size)` that holds embedded bytes.

_Why:_ a client that asks for a window must get all of it. What the batch answers without `view_name` on a record of several sequence views is an open question.

### The records list and the explorer

**API-54.** `GET /datasets/{id}/records` MUST take `include=view_previews`, and MUST answer 400 to any other value of `include`.

_Why:_ only the clients that show the previews ask for them.

**API-55.** With `include=view_previews`, each record of a page MUST carry `view_previews`, by logical name: `{resource, id, kind, preview_url, excerpt?}`. An image that holds no `uri` gets the kind `image` and `/datasets/{id}/images/{image id}/preview?size=256`. A sequence gets its frame 0, in the same way. A text gets the kind `text`, an empty `preview_url` and its first 160 characters. A point cloud gets the kind `image` and its preview route. The first table that holds a logical name wins, in this order: `calibrated_images`, `images`, `sequence_frames`, `texts`, `point_clouds`. A record with no such view MUST carry no `view_previews`.

_Why:_ a page of record cards shows a thumbnail or an excerpt of each view without one request per record. Today an image or a frame whose `uri` is an `http://` or `https://` address gets that `uri` as its `preview_url`, and the browser fetches it directly: how a browser reaches media held outside the dataset is the open question on the media. On a dataset that holds both `calibrated_images` and `images`, a row of `images` gets a preview route that answers 404 (API-49, and the open question on the two families). Today a view of `videos` gets no preview: no route serves a video, and no import makes its poster ([DATA-24](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media) and [DATA-23](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media), targets).

**API-56.** `GET /datasets/{id}/filters` MUST list, beside the records' own columns, each statistic the dataset computed per record whose column is in its table. Each MUST be named `record_statistics.<name>`, with its label and unit, and be sortable and filterable with the operators of its type. The values of these statistics that a record of a page (`GET /datasets/{id}/records`) carries MUST be in `computed_values`, by those names, with `null` where it has no value. When the dataset offers none, a record MUST carry no `computed_values`.

_Why:_ a statistic is computed to sort and filter the explorer on, and the name keeps it apart from a record's own column of the same name. Today, when the dataset offers at least one, each record of a page carries the value of every one: which statistics a page carries is the open question on a page of records.

**API-57.** The records list MUST sort by `id`, ascending, when it is asked for no sort. `order` MUST be `asc` or `desc`, in any case, and an order or a column that is unknown or cannot be sorted on MUST be answered 400. Records of equal values MUST follow their ids, in ascending order, whatever the direction.

_Why:_ pages must neither overlap nor skip a record, and the neighbors (API-62) must agree with the pages.

**API-58.** A sort on a computed column MUST put the records without a value last, whatever the direction.

_Why:_ a record without a value matches no comparison, and the records that have one are what the sort is for.

**API-59.** An explorer filter MUST be the token `column:operator:value`, split at its first two colons, and every filter of a request MUST apply. The operators MUST be, by the column's type: `eq`, `ne`, `in`, `nin` and `contains` for a text; `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in` and `nin` for a whole number; `eq`, `ne`, `lt`, `lte`, `gt` and `gte` for a decimal number; `eq` and `ne` for a yes-or-no; `eq`, `lt`, `lte`, `gt`, `gte` and `between` for a date. Only a column that holds one value, not a list, MUST be filterable or sortable. A filter that does not follow these MUST be answered 400.

_Why:_ the legacy explorer builds its chips, and the filters of the overview's bars, from this grammar, and a malformed filter is bad input, not a fault of the server.

**API-60.** An explorer's request MUST carry at most 8 filters, each value of at most 512 characters, and a free text of at most 256 characters. More MUST be answered 400. That holds for the records list, the neighbors, the overview and the filters of a search.

_Why:_ it bounds what one query compiles.

**API-61.** The free text `q` MUST match the records where it is part of a searchable column, whatever the case: a column of text that holds one value, being `comment` and the dataset's own columns. When the records have no such column, a free text MUST match no record. An empty free text MUST be ignored.

_Why:_ the person's text must not be ignored without a word.

**API-62.** `GET /datasets/{id}/records/{record_id}/neighbors` MUST read the explorer's request as the records list does, and answer `{prev, next, position, total}` in the order of the pages, with a position that counts from 1. A record the request does not keep, or that does not exist, MUST get a `null` `prev`, `next` and `position`, with the `total`.

_Why:_ the previous and next buttons of a record stay among the records the person browses.

**API-63.** In `GET /datasets/{id}/filters`, the records' base columns MUST come first, then the dataset's own columns, each group by name, then the statistics by label. `split` and `status` MUST list a bounded number of distinct values, with `values_complete` false when there are more. `search.modes` MUST hold `semantic` only when the default embedding space is `ready` or `partial`. `search.models` MUST list the names of the models whose space a search would read and that is `ready` or `partial`, the default first, and `search.spaces` every space with its health.

_Why:_ the interface offers only what the server accepts.

**API-64.** A statistics table that cannot be read MUST leave the explorer of its dataset offering no statistic, and MUST NOT fail `GET /datasets/{id}/filters` or the records list.

_Why:_ the explorer keeps working on the records' own columns. Today the app logs the failure.

### The statistics

**API-65.** `GET /statistics/definitions` MUST list the library's statistics that are still computed as they were composed, those per record first, then those per entity, each by label. `POST /statistics/definitions` MUST answer 201 with a new statistic, and 200 with the stored one, its label and description kept, when the library holds that statistic already. An unknown key, a label over 120 characters or a description over 1000 MUST be answered 422. What counts as the same statistic, and how a name already taken is made distinct, belong to `JOB` (`src/pixano/statistics/registry.py`).

_Why:_ a name, once stored, is the statistic's column for good: composing it again must not fork it.

**API-66.** `GET /datasets/{id}/statistics/choices` MUST answer what the dataset offers to compose a statistic from: its annotation kinds and how each can be measured, its entities' attributes and their values, and the filters on origin and review status. `GET /datasets/{id}/statistics/definitions` MUST answer the library's statistics, among those still computed as they were composed, that apply to the dataset.

_Why:_ a person composes only what the dataset can compute. Today both read only the tables the dataset declares, their rows, and the library's registry for the definitions. How the worker decides what to compute, from the same reading through its reader, belongs to `JOB`.

### The overview

**API-67.** `GET /datasets/{id}/overview` MUST read the explorer's request as the records list does, and count the records it keeps, their images and their entities. It MUST NOT run a semantic search.

_Why:_ the overview describes what the explorer shows. A semantic search ranks records, and the overview counts every record the filters keep.

**API-68.** A card of a column the explorer filters on MUST count the records that every other filter keeps, and say of each bar or value how many of its records its own filters keep (`filtered`, `selected`).

_Why:_ the bar clicked stays among the others rather than alone, as in Know Your Data.

**API-69.** The overview MUST give a card to each of the records' own fields of text, yes-or-no or number type that holds one value, but `id`, `created_at`, `updated_at` and `comment`; to each statistic computed per record; to the images' width, height, aspect ratio and format, and how many each record holds, where the frames of a video are not images; and to the entities' classes and each statistic computed per entity. A video dataset MUST get no media card. An entity counted MUST be one that is no part of another (no `parent_id`). A statistic's card MUST say when the statistic was computed (`computed_at`).

_Why:_ it follows the statistics of Know Your Data as closely as it can. The identifier, the timestamps and an annotator's note on a record are not data.

**API-70.** Whole numbers that span at most 40 values MUST get a bar each. Any other range MUST be cut into at most 20 bars of equal width. A value MUST be counted in the last bar whose start, as sent, is at most the value. A card of values MUST list the 20 values held most, and count the others together. A number that is not finite, an empty text, and an image size of zero, the one metadata did not give, MUST count as no value.

_Why:_ a value is counted by the very comparison that the bar's filter makes, so a bar and its filter keep the same records.

**API-71.** A card of the records' own fields, or of a statistic computed per record, MUST name the explorer's column that its bars and values filter on (`filter_column`).

_Why:_ a bar clicked gives the explorer the filters that keep its records. What the cards of the images and of the entities filter is an open question.

**API-72.** The overview MUST always give the splits of the records the request reads, in alphabetical order, with the records that name none last. Asked with `by_split`, each card MUST count its values per split, with what each split's share is counted out of (`counted_by_split`).

_Why:_ a split keeps its place and its color from card to card, and splits of any size compare by their shares.

**API-73.** The overview MUST list the default statistics that the dataset has not computed yet (`statistics_to_compute`).

_Why:_ an interface can then say that their cards are missing.

### Embeddings and semantic search

**API-74.** `POST /datasets/{id}/records/search` MUST read one model's embeddings: the model that `model` names, by its name or by its space's id, or the default space when it names none. A search `similar_to` a record MUST search with every vector the record holds. A body that carries both `similar_to` and `text` MUST be searched by `similar_to`. How records are ranked is [DATA-44](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene).

_Why:_ distances mean something within one model only, and a record is similar through any of its media.

**API-75.** A search MUST answer `{items, total, model, mode, k, space}`, each item a record with its `_distance` and its `view_previews`, by increasing distance. `total` MUST count the items answered, at most `k`, and is not the number of records that match. A search takes no `limit` or `offset`, and is never paged.

_Why:_ the interface shows the results as record cards, nearest first, with the previews of API-55. A search answers the `k` nearest records and no more, so there is nothing to page.

**API-76.** A search MUST answer 400 when it carries neither `text` nor `similar_to`, when it names a model the dataset holds no embeddings of, when the dataset holds none, and when `k` is less than 1.

_Why:_ no space can answer these requests, and the person who sent one can correct it.

**API-77.** A search MUST answer 503 when the space's table is missing, corrupt, empty or cannot be read; 409 when the dimension of the stored vectors, or of the query, is not the space's; 404 when the record that `similar_to` names has no vector; and 502 when the inference fails to embed the text.

_Why:_ a broken store of embeddings must give an error a person can act on, never a 500.

**API-78.** A text search MUST be answered 409 when the space records the checkpoint its vectors were computed with and the inference tells a different one for that model. An inference that tells none, or cannot be asked, embeds the query as before.

_Why:_ a query embedded by other weights ranks the stored vectors by a distance that means nothing.

**API-79.** The health of an embedding space MUST be one of `absent`, `missing_table`, `empty`, `dim_mismatch`, `corrupt`, `partial` and `ready`. A search MUST read only a space that is `ready` or `partial`.

_Why:_ the interface chooses what to offer, a search, a computation or a forced computation, from these words.

**API-80.** The health of a space MUST count the distinct media embedded against the dataset's still images. `partial` MUST mean that some image has no vector.

_Why:_ counting rows said "complete" with one camera of six embedded.

**API-81.** `GET /datasets/{id}/embedding-spaces` MUST list every space with its health, `{id, model_id, checkpoint, dim, default, status, detail, embedded_rows}`, in the order they were made, and `[]` when there is none.

_Why:_ a dataset keeps one table per model ([DATA-43](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene)), and a client manages each one apart.

**API-82.** `PUT /datasets/{id}/embedding-spaces/default` MUST take `{space_id}` and, unless API-84 or API-85 refuses it, make that space the default, the one a search naming no model reads, and answer it in the shape `GET /embedding-spaces` lists it.

_Why:_ a search that names no model reads the default space (API-74), and the client shows the space it made the default.

**API-83.** `DELETE /datasets/{id}/embedding-spaces/{space_id}` MUST, unless API-84 or API-85 refuses it, delete one model's embeddings and keep the others', and, when it deletes the default, hand the default to the first space left. Once it has deleted the space, it MUST answer 204.

_Why:_ a client drops one model's vectors without losing another's, and a search naming no model still finds a space.

**API-84.** The routes of the embedding spaces MUST name a space by its id only: a model's name, or a space the dataset does not hold, MUST be answered 404.

_Why:_ two checkpoints can share a model's name, so only the id names one space.

**API-85.** When the dataset's `embeddings.json` could not be read completely, which [DATA-43](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene) forbids rewriting, changing the default space and deleting a space MUST be answered 409, with a detail that names `force` as the way out. The 404 of a space the dataset does not hold (API-84) comes first: when no space could be read at all, these routes answer 404.

_Why:_ a partial rewrite would drop the spaces that the file holds and this build cannot read. A forced computation, which deletes every model's embeddings first, is the one way out (API-87).

**API-86.** `POST /datasets/{id}/embeddings/compute` MUST take `{model, provider_name, force}`. `provider_name` is optional, and names a connected inference provider: without it, the default provider computes the vectors. `force` defaults to false. Once the refusals of API-87 have passed, the route MUST answer 202 `{job_id}`, the id of the job that computes the vectors, which a client reads today at `GET /io/jobs/{id}` (`IO`).

_Why:_ the legacy app starts a computation and follows it by this id (`computeEmbeddings`, `ui/apps/pixano/src/lib/api/search.ts`). [ARCH-23](./architecture.md#execution-plane) (target) moves the computation to the queue: where the job runs, and where a client reads it, follow that target. This rule fixes the body and that the answer names the job. What the job does is described in the bullet on ARCH-23, and is not a rule.

**API-87.** `POST /datasets/{id}/embeddings/compute` MUST be refused before any job is created: 404 when the provider it names is not connected, or when it names none and no default is connected; 409, without `force`, in the case of API-85, or when the model's only space of that name has a health other than `absent`, `ready` and `partial`. It answers 400, after these, when the library is on S3 or is not the folder `library` of a data directory: today, because its job lives in the SQLite store of the imports ([ARCH-5](./architecture.md#control-plane), [ARCH-23](./architecture.md#execution-plane), targets).

_Why:_ a refused computation writes nothing, and the 409 says that `force` is the way out.

**API-88.** Once the job of a computation reads done, a search on the process that ran the computation MUST read the new vectors.

_Why:_ a client that sees it done, then searches, must find them. The app drops the dataset it holds before it marks the job done. Another process of a local library sees the vectors only when the computation changed `embeddings.json` (API-2), and nothing tells the other replicas: [ARCH-20](./architecture.md#media-cache-and-the-way-to-the-inference) (target) carries the change to every replica.

### Health

**API-89.** `GET /health/live` MUST answer 200 `{"status": "ok"}` as long as the process is alive, and test nothing else. It MUST answer on the event loop, however busy the threads of the data routes are.

_Why:_ what restarts a process must not restart it because a dependency is down, or because its threads are all busy ([ARCH-55](./architecture.md#observability)).

**API-90.** `GET /health/ready` MUST test the library's storage (a local folder that exists, or an S3 bucket that answers), and PostgreSQL when the deployment uses it (API-92), giving each a bounded time to answer. It MUST answer 503 until the storage, and PostgreSQL when it is tested, answer, and MUST be ready again as soon as they do, without a restart. A dependency that hangs MUST NOT hold the answer past its time, nor take the threads of the other.

_Why:_ a probe must learn whether the app can serve, and follow the dependency rather than the history of the process. Today the deployment uses PostgreSQL only when `PIXANO_DATABASE_URL` is set; [ARCH-2](./architecture.md#topology-and-deployment) (target) makes it always.

**API-91.** `GET /health/ready` MUST ask the default inference provider, when one is connected, giving it a bounded time of its own. An inference that fails or does not answer in that time MUST be named under `degraded`, and MUST NOT make the app not ready.

_Why:_ the app serves everything that needs no model without the inference ([ARCH-59](./architecture.md#inference-plane)). A probe waits one second unless told otherwise, as Kubernetes does: the inference's time is shorter, so a hung inference does not cost the probe its answer.

**API-92.** `GET /health/ready` MUST answer one body with 200 and with 503: `{status, missing, degraded, checks: {storage, postgresql, inference}}`, each check `{status, detail}` with the status `ok`, `unavailable` or `not_configured`. A dependency the deployment does not use MUST be `not_configured`, and fail nothing: the inference when none is connected, and today PostgreSQL when `PIXANO_DATABASE_URL` is unset, a mode that [ARCH-2](./architecture.md#topology-and-deployment) (target) removes. The detail MUST be a fixed sentence, and MUST NOT carry the error of the dependency.

_Why:_ an operator reads what is missing. The route answers without authentication today ([ARCH-35](./architecture.md#security), target), and the error of a database can name its host, its user or a password. Today the app logs that error as it is; [ARCH-42](./architecture.md#security) (target) keeps secrets out of the log.

**API-93.** `GET /health` MUST keep answering 200 `{"status": "ok"}` without testing anything.

_Why:_ the probes that already call it, such as the healthcheck of the Compose file, keep working.

## The routes today

This section describes the routes as they are. It decides nothing. Every route answers JSON unless the table says otherwise, and a dataset-scoped route answers 404 for an unknown dataset (API-1, a target: see its _Today:_ line).

### The app and the interface

| Method     | Path                                                        | What it does                                                                                     | Notes                                                                             |
| ---------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `GET`      | `/`                                                         | The page of the legacy app, or of the new UI when `ACTIVATE_UI_V1_0` is true and the cookie asks | Served by `pixano server run` only (`src/pixano/api/serve.py`); goes with ARCH-53 |
| `GET HEAD` | `/favicon.ico`, `/robots.txt`                               | The files of the legacy app, or 404                                                              | Served by `pixano server run` only                                                |
| `GET`      | `/{path}`                                                   | Redirects (307) to `/#/<path>`, or 404 under a prefix of the API (API-9)                         | Served by `pixano server run` only                                                |
| `GET`      | `/_app/*`, `/_legacy_app/*`                                 | The built files of the new UI and of the legacy app                                              | Static mounts; served by `pixano server run` only                                 |
| `GET`      | `/app_models/*`                                             | The files of the models folder (`MODELS_DIR`)                                                    | Static mount; no client calls it                                                  |
| `GET`      | `/app/ui`                                                   | `{new_ui_enabled}`, the value of `ACTIVATE_UI_V1_0`                                              | Read by the legacy app's header; goes with ARCH-53                                |
| `GET`      | `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` | The OpenAPI document, and the pages that show it                                                 | The pages load their scripts from `cdn.jsdelivr.net` (ARCH-4)                     |

### The datasets

| Method  | Path                           | What it does                                                                                          | Notes                                                                                                                                |
| ------- | ------------------------------ | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `GET`   | `/datasets`                    | Every dataset of the library, to every caller today (ARCH-35), with its count and its mosaic (API-10) | Each entry carries `num_records`, and `preview`: the mosaic as a base64 JPEG, or an empty string; writes a missing mosaic; no paging |
| `GET`   | `/datasets/{id}`               | The dataset: its tables, its features' values and its description (API-12)                            | Answers the dataset's paths on the server                                                                                            |
| `GET`   | `/datasets/{id}/info`          | The dataset's description                                                                             | Writes a missing mosaic; no client                                                                                                   |
| `GET`   | `/datasets/{id}/stats`         | Row counts per group of tables (API-13)                                                               |                                                                                                                                      |
| `GET`   | `/datasets/info/{id}/splits`   | Record counts per split and status (API-14)                                                           |                                                                                                                                      |
| `PATCH` | `/datasets/info/{id}/bookmark` | Toggles a bookmark (API-15)                                                                           | 409 when the dataset is busy                                                                                                         |

### Records and the explorer

| Method   | Path                                                   | What it does                                                        | Notes                                                                   |
| -------- | ------------------------------------------------------ | ------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `GET`    | `/datasets/{dataset_id}/records`                       | A page of records, filtered, searched and sorted (API-54 to API-61) | The parameter `where` is deprecated; a field that is `null` is left out |
| `GET`    | `/datasets/{dataset_id}/records/{id}`                  | One record                                                          |                                                                         |
| `POST`   | `/datasets/{dataset_id}/records`                       | Creates a record                                                    | No client                                                               |
| `PUT`    | `/datasets/{dataset_id}/records/{id}`                  | Updates a record                                                    | The legacy app sets a record's `status` with it                         |
| `DELETE` | `/datasets/{dataset_id}/records/{id}`                  | Deletes the record's row alone                                      | Its views, entities, annotations and embeddings stay; no client         |
| `GET`    | `/datasets/{dataset_id}/filters`                       | What the explorer can filter, sort and search on (API-56, API-63)   | Lists at most 100 values of `split` and of `status`                     |
| `GET`    | `/datasets/{dataset_id}/records/{record_id}/neighbors` | A record's place among the records the request keeps (API-62)       | The parameter `where` is deprecated                                     |
| `GET`    | `/datasets/{dataset_id}/overview`                      | The overview's cards (API-67 to API-73)                             | The parameter `where` is deprecated                                     |

### Views and media

Every list takes `limit`, `offset`, `view_name` (the logical name) and a raw `where`, and the lists of a whole dataset take `record_id` too. They answer a page in no fixed order.

| Method | Path                                                        | What it does                                                          | Notes                                                                                                                                                                                                       |
| ------ | ----------------------------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/datasets/{dataset_id}/images`, `/images/{id}`             | Image views, from `calibrated_images` or `images` (API-49)            |                                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/images/{id}/blob`                   | The image's bytes (API-50)                                            | No cache header                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/images/{id}/preview`                | The image's thumbnail (API-51)                                        | `Cache-Control: public, max-age=3600` and an `ETag`                                                                                                                                                         |
| `GET`  | `/datasets/{dataset_id}/texts`, `/texts/{id}`               | Text views                                                            |                                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/sframes`, `/sframes/{id}`           | Frames of sequences                                                   |                                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/sframes/{id}/blob`                  | The frame's bytes                                                     | No cache header                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/sframes/{id}/preview`               | The frame's thumbnail                                                 | As the image's                                                                                                                                                                                              |
| `GET`  | `/datasets/{dataset_id}/point-clouds`, `/point-clouds/{id}` | Point-cloud views                                                     |                                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/point-clouds/{id}/blob`             | The point cloud's bytes                                               | No cache header                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/point-clouds/{id}/preview`          | The image of the point cloud seen from above                          | Takes no size                                                                                                                                                                                               |
| `GET`  | `/datasets/{dataset_id}/records/{record_id}/images`         | One record's image views                                              |                                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/records/{record_id}/texts`          | One record's text views                                               |                                                                                                                                                                                                             |
| `GET`  | `/datasets/{dataset_id}/records/{record_id}/sframes`        | One record's frames                                                   | The legacy app sorts them by `frame_index` itself                                                                                                                                                           |
| `GET`  | `/datasets/{dataset_id}/records/{record_id}/sframes/batch`  | A window of a record's frames, as one multipart body (API-52, API-53) | `start_frame` from 0, and `batch_size` from 1 to 1000 (default 100); the whole batch is read into memory, then copied into one body; `X-Total-Frames` counts the frames of this answer, not of the sequence |
| `GET`  | `/datasets/{dataset_id}/records/{record_id}/point-clouds`   | One record's point clouds                                             |                                                                                                                                                                                                             |

### Resources

Each resource is served at `/datasets/{dataset_id}/{path}` (list, create) and `/datasets/{dataset_id}/{path}/{id}` (get, update, delete). Every list also takes a raw `where`, and answers a page in no fixed order.

| Resource              | Path                    | Methods                           | List filters                                                                       |
| --------------------- | ----------------------- | --------------------------------- | ---------------------------------------------------------------------------------- |
| Entities              | `entities`              | list, get, create, update, delete | `record_id`                                                                        |
| Entity dynamic states | `entity-dynamic-states` | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`, `frame_index` |
| Tracklets             | `tracklets`             | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`                               |
| Boxes                 | `bboxes`                | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`, `frame_index` |
| 3D boxes              | `bbox3ds`               | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`, `frame_index` |
| Masks                 | `masks`                 | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`, `frame_index` |
| Multi-paths           | `multi-paths`           | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`, `frame_index` |
| Keypoints             | `keypoints`             | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`, `tracklet_id`, `frame_index` |
| Classifications       | `classifications`       | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`                               |
| Relations             | `relations`             | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`                               |
| Messages              | `messages`              | list, get, create, update, delete | `record_id`, `view_name`, `source_type`                                            |
| Text spans            | `text-spans`            | list, get, create, update, delete | `record_id`, `entity_id`, `view_name`, `source_type`                               |
| Time series           | `timeseries`            | list, get                         | `record_id`, `view_name`, `frame_index`                                            |
| Embeddings            | `embeddings`            | list, get, create                 | `record_id`, `view_name`                                                           |

A create answers 201 and an update 200, each with the row as stored, and a delete 204 (API-26). An update takes `?prune_orphan_entity=`, and so does the delete of an annotation (API-37). The delete of an entity takes `?only_if_unnamed=` (API-35). The code also declares `entity_id` on the messages and the conversations, and answers it 500: a message names its entities in a list, `entity_ids`, and its table has no `entity_id` column. The `embeddings` resource reads the table `embeddings` alone, the one space of the datasets made before there was a table per model: on any other dataset it answers 404, and no client calls it.

| Method | Path                                                     | What it does                                       | Notes                                                                                                    |
| ------ | -------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `GET`  | `/datasets/{dataset_id}/conversations`                   | A page of conversations, rebuilt from the messages | Filters on `record_id`, `view_name`, `source_type`; creates a missing messages table (API-21); no client |
| `GET`  | `/datasets/{dataset_id}/conversations/{conversation_id}` | One conversation                                   | Creates a missing messages table (API-21); no client                                                     |

### Review and statistics

| Method | Path                                            | What it does                                                 | Notes     |
| ------ | ----------------------------------------------- | ------------------------------------------------------------ | --------- |
| `GET`  | `/datasets/{dataset_id}/review/next`            | The next record to review (API-45 to API-47)                 |           |
| `GET`  | `/statistics/definitions`                       | The library's statistics (API-65)                            | No client |
| `POST` | `/statistics/definitions`                       | Composes a statistic (API-65)                                | No client |
| `GET`  | `/datasets/{dataset_id}/statistics`             | The statistics the dataset computed, with their job and date | No client |
| `GET`  | `/datasets/{dataset_id}/statistics/choices`     | What the dataset offers to compose a statistic from (API-66) | No client |
| `GET`  | `/datasets/{dataset_id}/statistics/definitions` | The library's statistics that apply to the dataset (API-66)  | No client |

### Embeddings and search

| Method   | Path                                                 | What it does                                                                                              | Notes                                                                                               |
| -------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `POST`   | `/datasets/{dataset_id}/records/search`              | Semantic search by text or by a record (API-74 to API-78)                                                 | `k` defaults to 50; `where` in the body is deprecated                                               |
| `GET`    | `/datasets/{dataset_id}/embedding-spaces`            | Every space and its health (API-81)                                                                       | No client: the legacy app reads the spaces from `/filters`                                          |
| `PUT`    | `/datasets/{dataset_id}/embedding-spaces/default`    | Makes a space the default; takes `{space_id}` and answers that space (API-82)                             |                                                                                                     |
| `DELETE` | `/datasets/{dataset_id}/embedding-spaces/{space_id}` | Deletes a model's embeddings; answers 204 (API-83)                                                        | No client                                                                                           |
| `POST`   | `/datasets/{dataset_id}/embeddings/compute`          | Starts a computation; takes `{model, provider_name, force}` and answers 202 `{job_id}` (API-86 to API-88) | Polled at `GET /io/jobs/{id}` (`IO`); runs in a thread of the app (ARCH-23); 400 on a library on S3 |

### Health

| Method | Path            | What it does                                                      | Notes                                                                                                                                                                                                 |
| ------ | --------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/health/live`  | Whether the process answers (API-89)                              |                                                                                                                                                                                                       |
| `GET`  | `/health/ready` | Whether the app can serve, and what is missing (API-90 to API-92) | Gives the storage and PostgreSQL 2 s each, and the inference 0.5 s (`CHECK_TIMEOUT_S`, `OPTIONAL_CHECK_TIMEOUT_S`, `src/pixano/api/routers/health.py`); 503 when the storage or PostgreSQL is missing |
| `GET`  | `/health`       | Answers `ok` (API-93)                                             | Called by the healthcheck of the Compose file                                                                                                                                                         |

### The routes of other parts

`/io/*`, and the deprecated `POST /datasets/import` and `GET /datasets/import/{job_id}`, are `IO`'s. `/jobs/*` is `JOB`'s. `/inference/*` is `INF`'s.

### The configuration today

The app reads these variables of the environment (`src/pixano/api/settings.py`). Under `pixano server run`, the command's argument and options set the data directory, the S3 keys and the inference instead (`src/pixano/cli/server.py`), and `DATA_DIR` and the `AWS_*` variables are ignored.

| Variable                                                                                      | What it sets                                                                           |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `DATA_DIR`, `LIBRARY_DIR`, `MODELS_DIR`                                                       | The data directory, the library (a folder or an `s3://` address) and the models folder |
| `AWS_ENDPOINT`, `AWS_REGION`, `AWS_ACCESS_KEY`, `AWS_SECRET_KEY`                              | The S3 storage of a library on S3                                                      |
| `PIXANO_DATABASE_URL`                                                                         | The PostgreSQL of the job queue, shared with the worker; unset, there is no queue      |
| `PIXANO_EMBEDDINGS_AFTER_IMPORT`, `PIXANO_EMBEDDINGS_MODEL`, `PIXANO_STATISTICS_AFTER_IMPORT` | What an import queues after it (`IO`)                                                  |
| `CORS_ORIGINS`                                                                                | The origins allowed for cross-origin requests, as a JSON list (API-8)                  |
| `ACTIVATE_UI_V1_0`                                                                            | Whether the new UI can be reached                                                      |

## Open questions

- **Should a delete that leaves rows naming nothing be refused or cascaded?** Today the server does neither, for an entity (API-35), for a model's row a person rejects (API-44), or for a record: `DELETE /datasets/{id}/records/{id}` deletes the record's row alone, and leaves its views, entities, annotations and embeddings behind, although `Dataset.delete_records` cascades. A rule on the server is the only fix for every client.
- **What cache headers should the media routes send, how does a browser reach media held outside the dataset, and where does the API's version go in its routes?** [ARCH-19](./architecture.md#media-cache-and-the-way-to-the-inference) and [ARCH-54](./architecture.md#repository-packages-and-frontend) leave the headers and the version to this spec. Today only the previews carry `Cache-Control: public, max-age=3600` and an `ETag`, which no route checks to answer `304`, and the blobs and the frame batch carry none. No route carries a version. A view's `uri` is handed to the browser as it is (API-48, API-55). [DATA-22](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media) (target) allows a `uri` to be `https://` or `s3://`, and a browser cannot fetch `s3://`. The legacy app rewrites a relative `uri` to `media/<path>`, which no route serves.
- **How do the image routes serve a dataset that holds both `calibrated_images` and `images`?** Today the rows of `images` are out of them (API-49), and their previews answer 404 (API-55). No rule of `ARCH` or `DATA` forbids a dataset to hold both (`src/pixano/datasets/dataset_info.py`). Undecided: reading both tables, or naming the family in the route.
- **What does a person's save answer when it meets a write lease?** [ARCH-14](./architecture.md#data-plane) leaves it to `DATA` and to this spec. [DATA-41](./data-model.md#concurrency-write-leases-and-read-only-open) (target) sets a bounded wait, then a 409 with `Retry-After` and who holds the lease. Still to decide: the body of that 409, beside the codes of API-34, and the headers a client of another origin can read.
- **How soon must a replica see a change another process committed, and must it catch up an end-of-job event it missed while reconnecting?** [ARCH-20](./architecture.md#media-cache-and-the-way-to-the-inference) (target) says the change reaches every replica, and sets no bound. Today a process sees a rewritten `info.json` or `embeddings.json` of a local dataset at the next request (API-2), and the rows of a job once it receives the job's end (API-3), but not a row that another process writes, nor the end of a job whose event it lost.
- **In what order do the resource and view lists answer?** They sort nothing today: a page follows the order in which Lance scans the table, which a write or a compaction can change, so pages read while someone writes can overlap or skip a row. The records list sorts by id (API-57).
- **Does a resource list ignore a filter its kind does not declare, or refuse it with a 400?** Today it ignores it (API-20), so a client that misspells a filter gets every row of the dataset. The exception is `entity_id` on the messages and the conversations, which the code declares and answers 500 (see the resources table).
- **What does the time-series list filter on once [DATA-26](./data-model.md#physical-ai-multimodal-data-calibration-maps-and-media) (target) stores time-chunked streams?** A chunk has a `stream_name` and a timestamp window, and no `frame_index` or view. Today the time series take `record_id`, `view_name` and `frame_index` (API-20), on a layout of one row per frame.
- **How does an update clear a field that [DATA-13](./data-model.md#schemas-types-timestamps-and-serialization) (target) stores as `null`?** Today `null` in an update keeps the stored value (API-25's Why), and a client clears a field by sending its empty value, which DATA-13 forbids storing.
- **What becomes of the `embeddings` resource?** It takes list, get and create, and reads and writes the old single table `embeddings` only, outside `embeddings.json`, which [DATA-43](./data-model.md#embeddings-statistics-queries-and-lifecycle-hygiene) says declares every model's table. It answers without vectors (today, see API-23's Why), and 404 on a dataset without that table. The legacy interactive segmentation reads vectors from it (`ui/apps/pixano/src/lib/api/workspace.ts`), and gets none.
- **Does a person's edit of an entity accept the model's pending annotations that name it?** Today it does (`acceptances_of_entity_edit`, `src/pixano/api/review.py`, called by the service). An update of an entity that changes a field other than its `id`, `record_id`, `parent_id` and timestamps stores `accepted` every pending model annotation that names it by `entity_id`, a model's row with no status included, in every table of entity annotations that has the `review_status` column (see the open question on a dataset that is not migrated). It writes them in the same request, after the entity, under the same write lock on a local dataset. A row already `accepted` is left as it is, and an edit of the entity's dynamic state or a delete of the entity accepts nothing. The reason: what an annotation says can live in its entity, such as a model's class, and left pending, the annotation would be replaced by the next run of the model. What is undecided: the design of the jobs (`JOB`) calls this "a reading still to confirm". A person who fixes an entity's class accepts its pending masks, which nobody looked at, and an export of the accepted rows then includes them ([DATA-14](./data-model.md#annotations-provenance-and-review)).
- **Does the review queue propose the model rows of a dataset that is not migrated?** Once [DATA-52](./data-model.md#layout-versioning-and-migrations-spec_version) (target) projects `review_status` `''` on it, [DATA-14](./data-model.md#annotations-provenance-and-review) counts them pending, but no decision on them can be stored until the dataset is migrated ([DATA-53](./data-model.md#layout-versioning-and-migrations-spec_version), target). Today the queue skips their tables (API-46), and so does the acceptance of an entity's edit.
- **Should the cards of the images and of the entities filter the explorer?** Today they name no `filter_column`, and neither does the card of the count of images per record (`src/pixano/datasets/queries/overview.py`): the explorer filters on the records' columns only, and none of these values is one. Whether a click on their bars should filter the records is not decided: it would need the explorer to filter on images and entities.
- **Does a page of records carry every statistic?** Today each record of a page carries the value of every statistic computed per record (API-56), with no way to ask for some only, and no route stops computing a statistic or deletes one (`src/pixano/api/routers/records.py`). Each page grows with each statistic composed. Undecided: a projection that names the columns a page carries, a way to retire a statistic, or both.
- **Does a computation of embeddings embed records or media?** The computation in the app embeds one image per record (see the bullet on ARCH-23), while the health of a space counts the still images embedded (API-80). On a dataset of several images per record, the space stays `partial` after every computation, forced or not, and the interface keeps offering one. The embeddings job of the worker embeds each medium. What a computation covers, and what resuming it skips, waits for the move to the queue ([ARCH-23](./architecture.md#execution-plane), `JOB`).
- **What does the frame batch answer without `view_name` on a record of several sequence views?** A 400, the frames of one view, or the frames of every view, each part naming its view: a part names no view today (API-52), so two parts of two cameras can carry the same frame index. Today the query keeps `batch_size` rows before it sorts them (`Dataset.get_temporal_view_batch`, `src/pixano/datasets/dataset.py`), so the parts are at most `batch_size` frames of the window, and which ones depends on the order in which the table is scanned. The legacy player always sends `view_name` (`streamViewFrameBatch`, `ui/apps/pixano/src/lib/api/viewsApi.ts`).
- **Does `/app_models` stay?** It serves every file of the models folder to whoever reaches the app, and no client calls it.

## Decision log

- 2026-11-26: first draft: the rules the old docs/ held (`FRONTEND_ARCHITECTURE.md`, `backend-processing.md`, `writing-a-job-kind.md`, `OPEN_QUESTIONS.md`, `data-import-export.md`, `running-by-hand.md`), checked against the code, and the routes and contracts of the code that clients rely on ([#877](https://github.com/pixano/pixano/pull/877)).
