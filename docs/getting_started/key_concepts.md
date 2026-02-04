# Key concepts

## What Pixano does

Pixano provides two main capabilities:

1. **Dataset management** in a fast, columnar data format based on the [Lance](https://lancedb.github.io/lance/) format and the [LanceDB](https://lancedb.github.io/lancedb/) vector database.
2. **An annotation web platform** powered by AI.

## Architecture

Pixano has **three** layers:

- The **backend** manages datasets: creation, insertions, deletions, updates, and statistical computations.
- The **REST API** handles HTTP requests and translates them into backend operations.
- The **UI** allows users to visualize data and interact with it to add, update, or delete annotations and entities.

## Schema groups

Every dataset is composed of tables grouped by purpose. Pixano defines six **schema groups**:

| Group         | Description                                      | Example             |
|---------------|--------------------------------------------------|----------------------|
| **Item**      | One row per dataset entry (metadata, split, ...) | `Item`               |
| **View**      | Media attached to an item                        | `Image`, `Video`     |
| **Entity**    | Objects or tracks within an item                 | `Entity`             |
| **Annotation**| Labels attached to entities                      | `BBox`, `KeyPoints`, `CompressedRLE` |
| **Embedding** | Vectors for semantic search                      | `Embedding`          |
| **Source**    | Provenance of annotations/predictions            | `Source`             |

Each group has a base class (e.g. `Item`, `View`, `Entity`, `Annotation`) that you can subclass to add domain-specific fields:

```python
from pixano.features import Entity

class DetectedObject(Entity):
    category: str = ""
```

## Library, media, and models

Pixano organizes data around three directories:

- **Library** -- contains all datasets (each dataset is a LanceDB database). The path is provided at launch time.
- **Media** -- holds images, videos, and other files referenced by views. Also provided at launch time.
- **Models** -- optional directory for model files used by AI-assisted features (e.g. SAM for interactive segmentation).

## On-disk layout

Each dataset is a directory inside the library with this structure:

```text
<dataset>/
  info.json               # name, description, workspace type
  schema.json             # tables, fields, relations, groups
  features_values.json    # value constraints for fields (optional)
  stats.json              # dataset statistics (optional)
  preview.png             # preview image (optional)
  db/                     # LanceDB tables (one per schema)
```

Media files live in the separate media directory, and views reference them by relative URL.

## Common Python operations

```python
from pathlib import Path
from pixano.datasets import Dataset

# Open a dataset
ds = Dataset(Path("./library/my_dataset"), media_dir=Path("./media"))

# Read items
items = ds.get_dataset_items(limit=20, skip=0)

# Read a specific table
images = ds.get_data("image", limit=5)

# Add annotations
ds.add_data("bboxes", [bbox1, bbox2])

# Semantic search (requires precomputed embeddings)
top_items, distances, ids = ds.semantic_search("car on road", "image_embedding", limit=50)
```

For a full walkthrough, see the [Build and query a dataset](../tutorials/dataset.md) tutorial.
