## Pixano dataset organization

This guide gives newcomers a concise but in-depth tour of how datasets are structured and manipulated in Pixano. It explains the on-disk layout, the core runtime models, and how data flows through builders, queries, and integrity checks. It ends with concrete improvement suggestions.

### On-disk layout

A Pixano dataset is a directory with a LanceDB database and a few JSON sidecar files:

```text
<dataset_root>/
  info.json                 # high-level metadata (id, name, description, workspace)
  schema.json               # dataset logical schema (tables, fields, relations, groups)
  features_values.json      # value constraints for specific fields (optional)
  stats.json                # dataset statistics (optional)
  preview.png               # preview image (optional)
  previews/                 # additional previews
  db/                       # LanceDB database directory (one table per logical schema)
  media/                    # media storage (default path; can be external)
```

- info.json is serialized/deserialized by `pixano.datasets.DatasetInfo`.
- schema.json is serialized/deserialized by `pixano.datasets.DatasetSchema` and drives the logical model.
- features_values.json stores field-level constraints via `pixano.datasets.DatasetFeaturesValues` (see Constraints below).

### Core concepts and schema groups

Every dataset is composed of logical tables grouped by purpose, defined in `pixano.features.schemas.schema_group.SchemaGroup`:

- item: the unique per-item record (exactly one table of this group).
- views: per-item views such as `Image`, `Video`, `Text`, etc.
- entities: objects or tracks associated to a view or item.
- annotations: labels attached to entities/views/items (e.g., `BBox`, `Keypoints`, classification, IE, etc.).
- embeddings: vectors computed from a view (semantic search, retrieval).
- source: metadata about the provenance of annotations/predictions.

Each logical table is a Pydantic model subclassing `pixano.features.BaseSchema` (itself a `lancedb.pydantic.LanceModel`). All tables contain common fields: `id`, `created_at`, `updated_at`. Most domain-specific tables include typed references like `item_ref`, `view_ref`, `entity_ref`, `source_ref`.

### DatasetSchema and relations

`DatasetSchema` maps table names to schema classes and encodes relations between the `item` table and all other tables. Relations use `SchemaRelation` with the usual cardinalities:

- one_to_one: each item has at most one related row in the target table
- one_to_many: each item has a list of related rows
- many_to_one and many_to_many are supported in the model, but most of the current code paths focus on `item -> {one_to_one, one_to_many}`

Groups are inferred automatically based on the schema base class and serialized to JSON to aid UI and tooling.

### DatasetItem: a unified per-item view

At runtime, the dataset exposes a unified, strongly-typed item model synthesized from the schema: `pixano.datasets.DatasetItem`. It flattens the `item` table fields directly on the object and attaches related tables as attributes based on relations:

- one_to_one tables become optional attributes
- one_to_many tables become lists

Example (simplified):

```python
from pixano.datasets import Dataset

ds = Dataset(<path>)
item = ds.get_dataset_items(ids="123")
print(item.image)        # one_to_one view
print(len(item.bboxes))  # one_to_many annotations
```

The dataset dynamically builds `DatasetItem` from `schema.json`, so it always reflects the current logical schema without additional code generation.

### Querying data

The `Dataset` class is the main entry point:

- `open_table(name)` opens a LanceDB table by name.
- `get_data(table_name, ...)` returns Pydantic rows for a specific table with filters:
  - filter by ids, or by `item_ids` (items whose related rows you want), or by a SQL `where` expression
  - `limit` and `skip` for pagination
  - optional `order` on selected columns
- `get_dataset_items(...)` returns unified `DatasetItem` objects (joins item + all related tables, excluding embeddings by default).
- `get_all_ids(table_name=...)` lists ids, optionally sorted.
- `semantic_search(query, table_name, limit, skip)` runs ANN search on a view embedding table and returns top items with distances, using LanceDB.

Under the hood the query layer uses `TableQueryBuilder`, which composes select/where/limit/offset/order_by. It currently materializes data to Arrow and (optionally) uses DuckDB to apply sorting; this keeps row order stable for Pydantic conversion.

### Adding, updating, and deleting data

`Dataset` provides safe mutation APIs with optional integrity checks:

- `add_data(table_name, list[BaseSchema])` inserts rows; stamps `created_at/updated_at`.
- `update_data(table_name, list[BaseSchema], return_separately=False)` upserts by `id`; sets `updated_at`, keeps prior `created_at` when matched.
- `delete_data(table_name, ids)` deletes rows by id and returns ids not found.
- `add_dataset_items(DatasetItem|list)` and `update_dataset_items(list)` operate at the unified item level by splitting/merging rows across tables.

Integrity is enforced via helpers in `pixano.datasets.utils.integrity` (e.g., id uniqueness, reference sanity). You can switch behavior with `raise_or_warn`.

### Constraints (features_values.json)

`DatasetFeaturesValues` stores enumerations and allowed values used by the UI and validation. You can add or update constraints programmatically:

```python
ds.add_constraint(
    table="item",
    field_name="category",
    values=["car", "bus", "pedestrian"],
    restricted=True,
)
```

Constraints are grouped by schema group (`item`, `views`, `entities`, `annotations`) and persisted to `features_values.json`.

### Building datasets programmatically

To create datasets from raw sources, inherit from `pixano.datasets.builders.DatasetBuilder` and implement `generate_data()` yielding rows per table following the logical schema:

```python
from pixano.datasets.builders import DatasetBuilder
from pixano.datasets import DatasetInfo

class MyBuilder(DatasetBuilder):
    def generate_data(self):
        # yield dict[table_name, BaseSchema|list[BaseSchema]]
        for sample in my_source:
            yield {
                "item": ...,       # Item
                "image": ...,      # View
                "entities": [...], # Entities
                "bboxes": [...],   # Annotations
            }

builder = MyBuilder(target_dir, dataset_item=..., info=DatasetInfo(name="My DS"))
ds = builder.build(mode="create", check_integrity="raise")
```

Builder utilities:

- `create_tables`/`open_tables` to manage LanceDB tables.
- `add_source` and `add_ground_truth_source` to track provenance in the `source` table.
- Optional `flush_every_n_samples` and `compact_every_n_transactions` to tune write performance.

### Workspace types

`DatasetInfo.workspace` indicates how the UI/workflows will present the data (e.g., `image`, `video`, `image_vqa`, `image_text_entity_linking`, or `undefined`).

### Suggested improvements

These changes would improve performance, consistency, and developer UX:

- Query performance and memory
  - Push down filters/limits to LanceDB whenever possible, and only fall back to DuckDB for ORDER BY.
  - Provide iterator-based APIs (e.g., `iterate_data`, `iterate_dataset_items`) to stream results in chunks.

- Ordering and pagination
  - Expose stable, index-backed ordering facilities; document best practices for large datasets (cursor-based pagination using ids).

- Many-to-many and non-item relations
  - The schema supports `MANY_TO_MANY`, but `get_dataset_items` currently focuses on `item`-centric joins. Add examples, tests, and helper methods for many-to-many retrieval and mutation.

- Consistent exceptions
  - Prefer domain-specific errors (e.g., `DatasetAccessError`) over generic `ValueError` across all dataset and query APIs.

- Constraints management
  - Add `remove_constraint` and `list_constraints` helpers; allow constraints on nested fields (e.g., `metadata.subfield`).

- Embedding utilities
  - Improve `compute_view_embeddings` to infer or validate `shape` automatically from the registered embedding function; add batched inference and progress reporting hooks.

- Schema JSON minimalism
  - Consider deriving `groups` on load rather than persisting them, to reduce duplication and drift risk.

- DX and docs
  - Provide a minimal end-to-end builder template (cookiecutter) and CLI to scaffold `DatasetBuilder` projects.
  - Enrich API docstrings with small runnable snippets (e.g., `get_data`, `update_data`, `semantic_search`).

### Quick reference: common operations

```python
# Open a dataset
ds = Dataset(<path>)

# Get 20 items after skipping 100
items = ds.get_dataset_items(limit=20, skip=100)

# Read views for specific items
views = ds.get_data("image", item_ids=[i.id for i in items])

# Add new annotations
ds.add_data("bboxes", [bbox1, bbox2])

# Upsert a whole dataset item
ds.update_dataset_items([updated_item])

# Semantic search over an embedding table
top_items, distances, full_ids = ds.semantic_search("car on street", "image_embedding", limit=50)
```

With these foundations, you can navigate Pixano datasets confidently and extend them for your use case.


