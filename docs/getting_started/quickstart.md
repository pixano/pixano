# Quickstart: Import a Dataset with Pre-annotations

This guide walks you through importing an annotated dataset into Pixano in three steps: **init** your data directory, **import** your dataset, and **serve** the application. By the end you will have a running Pixano instance displaying images with bounding-box pre-annotations. See [Installing Pixano](installing_pixano.md) for setup instructions.

## Prerequisites

- Python 3.10+ installed
- Pixano installed:

  ```bash
  pip install pixano
  ```

??? note "Running from source with uv"

    Clone the repository and install with [uv](https://docs.astral.sh/uv/):

    ```bash
    git clone https://github.com/pixano/pixano.git
    cd pixano
    uv sync
    ```

    When running from source, prefix every command with `uv run` (e.g. `uv run pixano init ./my_data`).

## Step 1 — Initialize Your Data Directory

Create the directory structure Pixano needs to store datasets, media files, and models:

```bash
pixano init ./my_data
```

This creates the following tree:

```
my_data/
  library/   # LanceDB dataset storage
  media/     # Imported media files (images, videos)
  models/    # Model files for inference
```

## Step 2 — Prepare and Import Your Dataset

Pixano imports datasets from a source directory organized by **splits** (e.g. `train/`, `val/`). Each split folder contains the media files and an optional `metadata.jsonl` file with pre-annotations.

### Object Detection

You have images with bounding-box annotations and want to import them into Pixano.

**Organize your source folder**

```
street_objects/
  train/
    img_001.jpg
    img_002.jpg
    img_003.jpg
    metadata.jsonl
  val/
    img_004.jpg
    img_005.jpg
```

Two rules:

- Each **subfolder** is a split.
- A **`metadata.jsonl`** file inside a split folder provides pre-annotations for that split. Splits without one (like `val/` above) import images with no pre-annotations.

**Define your schema**

The base `Entity` class has no domain-specific attributes, so you need a custom schema to attach fields like `category` to your objects. Save this file as `schema.py`:

```python
# schema.py
from pixano.features import Entity
from pixano.datasets.workspaces import DefaultImageDatasetItem


class DetectedObject(Entity):
    category: str = ""


class StreetObjectsDatasetItem(DefaultImageDatasetItem):
    objects: list[DetectedObject]  # overrides default Entity table
    image_source: str = ""         # item-level metadata
```

Extending `Entity` lets you add custom attributes to each detected object. Extending `DefaultImageDatasetItem` gives you the standard image tables out of the box — you only need to override what you want to customize.

??? note "What's in the default schema?"

    `DefaultImageDatasetItem` provides the following attributes. Fields you don't override are included automatically.

    | Attribute    | Type                   | Stored in                     |
    |--------------|------------------------|-------------------------------|
    | `image`      | `Image`                | `image` table (view)          |
    | `objects`    | `list[Entity]`         | `objects` table (entities)    |
    | `bboxes`     | `list[BBox]`           | `bboxes` table (annotations)  |
    | `masks`      | `list[CompressedRLE]`  | `masks` table (annotations)   |
    | `keypoints`  | `list[KeyPoints]`      | `keypoints` table (annotations) |

    In the example above, `objects` is overridden with `list[DetectedObject]` to add the `category` field. The `image_source` field does not correspond to any schema group, so it is stored as item-level metadata in the `item` table.

**Write the metadata.jsonl**

Create a `metadata.jsonl` file in each split folder that has pre-annotations. Each line is a JSON object describing one image:

**`street_objects/train/metadata.jsonl`**

```json
{"image": "img_001.jpg", "image_source": "dashcam", "objects": {"bboxes": [[0.12, 0.25, 0.15, 0.30], [0.55, 0.10, 0.20, 0.45]], "category": ["car", "pedestrian"]}}
{"image": "img_002.jpg", "image_source": "dashcam", "objects": {"bboxes": [[0.30, 0.40, 0.08, 0.12]], "category": ["bicycle"]}}
{"image": "img_003.jpg", "image_source": "drone"}
```

Format rules:

- **`image`** matches the view field name in the schema and points to the image file in the same folder.
- **`image_source`** is stored as item-level metadata (it does not match any schema table name).
- **`objects`** matches the entity field name in the schema. Its value is a dict containing entity attributes and annotation data.
- **`bboxes`** inside `objects` matches the annotation table name. Each bounding box is `[x, y, w, h]`.
- **Entity attributes** (`category`) are parallel arrays — one value per bounding box.
- **Items without `objects`** (like `img_003.jpg`) have no pre-annotations.
- **Coordinates** are auto-detected as normalized when all values fall within [0, 1].

??? note "Format details"

    The `metadata.jsonl` format mirrors the schema structure:

    - **Top-level keys** that match a view field (e.g. `image`) are treated as view references — the value is the filename relative to the split folder.
    - **Top-level keys** that match an entity field (e.g. `objects`) contain a nested dict. Keys inside this dict that match annotation table names (e.g. `bboxes`) are parsed as annotation data. All other keys are treated as entity attributes.
    - **Top-level keys** that don't match any view or entity field (e.g. `image_source`) are stored as item-level metadata.
    - Entity attributes and annotation arrays must have the same length — each index corresponds to one object.

**Run the import**

```bash
pixano data import ./my_data ./street_objects \
    --name "Street Objects" \
    --schema ./schema.py:StreetObjectsDatasetItem
```

Common options:

| Option     | Description                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `--name`   | Dataset name. Defaults to the source directory name.                              |
| `--type`   | Dataset type: `image` (default), `video`, or `vqa`.                               |
| `--mode`   | `create` (default, fails if exists), `overwrite`, or `add` (append).              |
| `--schema` | Custom schema as `path/to/file.py:ClassName`. Uses the default schema if omitted. |

??? note "Alternative: build the dataset with Python"

    You can also build the dataset programmatically:

    ```python
    from pathlib import Path
    from pixano.datasets import DatasetInfo
    from pixano.datasets.builders import ImageFolderBuilder

    builder = ImageFolderBuilder(
        media_dir=Path("./my_data/media"),
        library_dir=Path("./my_data/library"),
        dataset_item=StreetObjectsDatasetItem,
        info=DatasetInfo(
            name="Street Objects",
            description="Street scene images with object detection pre-annotations",
        ),
        dataset_path="street_objects",
    )

    dataset = builder.build(mode="create")
    print(f"Dataset built: {dataset.num_rows} items")
    ```

#### Try it: Pascal VOC 2007

The repository includes a ready-to-run example that downloads a sample of the [Pascal VOC 2007](http://host.robots.ox.ac.uk/pascal/VOC/voc2007/) dataset and produces a Pixano-compatible folder. Use it to test the full import workflow with real data.

**1. Generate the sample folder**

```bash
pip install pillow                        # required by the script
python examples/voc/generate_sample.py ./voc_sample --num-samples 50
```

This downloads VOC 2007, samples 50 images per split, converts the XML annotations to `metadata.jsonl` files with normalized bounding boxes, and writes everything to `./voc_sample/`.

The resulting folder looks like:

```
voc_sample/
  train/
    000032.jpg
    000045.jpg
    ...
    metadata.jsonl
  validation/
    000007.jpg
    000019.jpg
    ...
    metadata.jsonl
```

Each line in `metadata.jsonl` follows the format described above:

```json
{"image": "000032.jpg", "objects": {"bboxes": [[0.078, 0.090, 0.756, 0.792], ...], "category": ["aeroplane", ...], "is_difficult": [false, ...]}}
```

**2. Review the schema**

The example schema is at `examples/voc/schema.py`:

```python
from pixano.datasets.workspaces import DefaultImageDatasetItem
from pixano.features import Entity


class VOCObject(Entity):
    category: str = ""
    is_difficult: bool = False


class VOCDatasetItem(DefaultImageDatasetItem):
    objects: list[VOCObject]
```

Same pattern as the street-objects example — a custom `Entity` subclass with domain-specific attributes, plugged into `DefaultImageDatasetItem`.

**3. Import and serve**

```bash
pixano init ./my_data
pixano data import ./my_data ./voc_sample \
    --name "VOC 2007 Sample" \
    --schema examples/voc/schema.py:VOCDatasetItem
pixano server run ./my_data
```

Open `http://127.0.0.1:7492` to browse the imported VOC images and bounding boxes.

### Visual Question Answering

You have images with question-answer pairs and want to import them into Pixano.

**Organize your source folder**

```
vqa_data/
  train/
    image_001.jpg
    image_002.jpg
    metadata.jsonl
  val/
    image_003.jpg
    metadata.jsonl
```

Same rules as object detection: each subfolder is a split, and a `metadata.jsonl` provides the annotations.

**Write the metadata.jsonl**

For VQA datasets, each line in `metadata.jsonl` describes one image and its associated question-answer conversations:

**`vqa_data/train/metadata.jsonl`**

```json
{"image": "image_001.jpg", "conversations": [{"question": {"content": "What color is the car?", "question_type": "OPEN"}, "responses": [{"content": "red", "user": "annotator_0"}, {"content": "dark red", "user": "annotator_1"}]}, {"question": {"content": "How many people are visible?", "question_type": "OPEN"}, "responses": [{"content": "3", "user": "annotator_0"}]}]}
{"image": "image_002.jpg", "conversations": [{"question": {"content": "Is it raining?", "question_type": "OPEN"}, "responses": [{"content": "no", "user": "annotator_0"}]}]}
```

Format rules:

- **`image`** points to the image file in the same folder.
- **`conversations`** is a list of question-answer exchanges for the image.
- Each conversation has a **`question`** with `content` (the question text) and `question_type` (`"OPEN"` for free-form answers).
- **`responses`** is a list of answers. Each response has `content` (the answer text) and an optional `user` field to distinguish annotators.
- An image can have **multiple conversations** (multiple questions about the same image).

??? note "Multiple-choice questions"

    For multiple-choice questions, set `question_type` to `"multi_choice"` and add a `choices` list:

    ```json
    {"question": {"content": "What is in the image?", "question_type": "multi_choice", "choices": ["a cat", "a dog", "a bird", "a fish"]}, "responses": [{"content": "a cat"}]}
    ```

**Run the import**

```bash
pixano data import ./my_data ./vqa_data \
    --name "VQA Data" \
    --type vqa
```

The `--type vqa` flag tells Pixano to use the VQA folder builder, which parses the `conversations` format. No custom schema is required — the default `DefaultVQADatasetItem` schema handles images, conversations, messages, objects, bounding boxes, masks, and keypoints.

??? note "Alternative: build the dataset with Python"

    You can also build the dataset programmatically:

    ```python
    from pathlib import Path
    from pixano.datasets import DatasetInfo
    from pixano.datasets.builders import VQAFolderBuilder
    from pixano.datasets.workspaces import DefaultVQADatasetItem

    builder = VQAFolderBuilder(
        media_dir=Path("./my_data/media"),
        library_dir=Path("./my_data/library"),
        dataset_item=DefaultVQADatasetItem,
        info=DatasetInfo(
            name="VQA Data",
            description="VQA dataset with question-answer pairs",
        ),
        dataset_path="vqa_data",
    )

    dataset = builder.build(mode="create")
    print(f"Dataset built: {dataset.num_rows} items")
    ```

#### Try it: VQAv2

The repository includes a ready-to-run example that downloads a sample of a small [VQAv2](https://visualqa.org/) subset from HuggingFace and produces a Pixano-compatible folder. It also demonstrates how to combine VQA with object annotation using a custom schema. Use it to test the full VQA import workflow with real data.

**1. Generate the sample folder**

```bash
pip install datasets pillow              # required by the script
python examples/vqav2/generate_sample.py ./vqav2_sample --num-samples 50
```

This downloads a small VQAv2 subset, samples 50 images with their questions, and writes everything to `./vqav2_sample/`.

The resulting folder looks like:

```
vqav2_sample/
  validation/
    000000.jpg
    000001.jpg
    ...
    metadata.jsonl
```

Each line in `metadata.jsonl` describes one image with its question and answer:

```json
{
  "image": "000000.jpg",
  "conversations": [
    {
      "question": {
        "content": "Where are the kids riding?",
        "question_type": "OPEN"
      },
      "responses": [{ "content": "carnival ride" }]
    }
  ]
}
```

**2. Review the schema**

The example uses a custom schema at `examples/vqav2/schema.py` to add object annotation support alongside the VQA task:

```python
from pixano.datasets.workspaces import DefaultVQADatasetItem
from pixano.features import Entity


class ObjectEntity(Entity):
    """Custom entity for object annotation with category and occlusion info."""

    category: str = ""
    subcategory: str = ""
    is_occluded: bool = False


class VQAv2DatasetItem(DefaultVQADatasetItem):
    """Dataset item for VQAv2 with object annotation support."""

    objects: list[ObjectEntity]
```

Same pattern as the VOC example — a custom `Entity` subclass with domain-specific attributes, plugged into `DefaultVQADatasetItem`.

**3. Import and serve**

```bash
pixano init ./my_data
pixano data import ./my_data ./vqav2_sample \
    --name "VQAv2 Sample" \
    --type vqa \
    --schema examples/vqav2/schema.py:VQAv2DatasetItem
pixano server run ./my_data
```

Open `http://127.0.0.1:7492` to browse the imported VQA images, questions, and answers.

## Step 3 — Launch the Server

```bash
pixano server run ./my_data
```

Open `http://127.0.0.1:7492` in your browser to explore and annotate your dataset.

- `--host` — bind address (e.g. `0.0.0.0` for network access). Default: `127.0.0.1`.
- `--port` — port number. Default: `7492`.

## Explore Your Data

The web UI lets you browse items, view annotations, and start annotating. You can also interact with your data programmatically.

??? note "Explore the REST API"

    While the server is running, interactive API documentation is available at:

    - **Swagger UI**: `http://127.0.0.1:7492/docs`
    - **ReDoc**: `http://127.0.0.1:7492/redoc`

    **List all datasets** and find the dataset ID:

    ```bash
    curl -s http://localhost:7492/datasets/info | python -m json.tool
    ```

    The response includes an `id` field for each dataset. Use this ID in subsequent requests (referred to as `<DATASET_ID>` below).

    **Get items** (first 3):

    ```bash
    curl -s 'http://localhost:7492/items/<DATASET_ID>?limit=3' | python -m json.tool
    ```

    **Get image views**:

    ```bash
    curl -s 'http://localhost:7492/views/<DATASET_ID>/image?limit=2' | python -m json.tool
    ```

    **Get entities** (objects with category):

    ```bash
    curl -s 'http://localhost:7492/entities/<DATASET_ID>/objects?limit=5' | python -m json.tool
    ```

    **Get bounding boxes for a specific item**:

    ```bash
    curl -s 'http://localhost:7492/annotations/<DATASET_ID>/bboxes?item_ids=<ITEM_ID>' | python -m json.tool
    ```

    **Browse dataset** (same endpoint the UI uses):

    ```bash
    curl -s 'http://localhost:7492/browser/<DATASET_ID>?limit=10' | python -m json.tool
    ```

??? note "Verify with the Python API"

    Load the dataset and inspect items to confirm the import worked:

    ```python
    from pathlib import Path
    from pixano.datasets import Dataset

    dataset = Dataset(Path("./my_data/library/street_objects"), media_dir=Path("./my_data/media"))
    items = dataset.get_dataset_items(limit=3)
    for item in items:
        print(f"Item {item.id} | split={item.split}")
    ```

## Next Steps

- [Build and query a dataset](../tutorials/dataset.md) — deeper dive into dataset creation and querying
- [Pre-annotation](../tutorials/pre_annotation.md) — more pre-annotation formats and workflows
- [Semantic search](../tutorials/semantic_search.md) — search your dataset using embeddings
