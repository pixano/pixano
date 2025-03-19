# Build a Pixano library

## Context

In this tutorial, we will build a library consisting of one dataset from a folder dataset stored in the `./assets/health_images/` folder with a unique subfolder `all/` which will later be considered as a split.

It contains 10 images of human parts from several image sources (MRI, microscope, and high-resolution photos). A `metadata.jsonl` also provides annotations, bounding boxes and keypoints, associated to these images.

## Build the Dataset

### Describe your dataset

To create a Pixano `Dataset`, a `DatasetBuilder` needs a pythonic description of the dataset item based on a Pydantic's [BaseModel](https://docs.pydantic.dev/latest/api/base_model/).

To do so, Pixano provides the `pixano.datasets.DatasetItem` class that already has the attributes `id` and `split` to uniquely identify an item and categorize the items respectively.

To define a custom `DatasetItem`, simply create a sublcass of `DatasetItem` that define all the features of your dataset.

In our case we have:

- `image_type`: a string metadata.
- `image`: the unique view of the item that is an Image.
- `objects`: the entites of an item. Think of it as a common identifier for multiple annotations.
- `bboxes`: the bounding boxes of an item.
- `masks`: the masks of an item.
- `keypoints`: the keypoints of an item.

This is how it can be defined in code:

```python
from pixano.datasets import DatasetItem
from pixano.features import BBox, CompressedRLE, Entity, Image, KeyPoints

class EntityWithCategory(Entity):
    category: str

class HealthDatasetItem(DatasetItem):
    image: Image
    objects: list[EntityWithCategory]
    bboxes: list[BBox]
    masks: list[CompressedRLE]
    keypoints: list[KeyPoints]
    image_type: str
```

Notice that when multiple elements are attached to an item we use the `list` type.

Another possibility is to use a predefined `DatasetItem` for image datasets:
```python
class DefaultImageDatasetItem(DatasetItem):
    """Default Image DatasetItem Schema."""

    image: Image
    objects: list[Entity]
    bboxes: list[BBox]
    masks: list[CompressedRLE]
    keypoints: list[KeyPoints]
```
This is the one used by `ImageFolderBuilder` if no schema is provided.

We can override it to add or modify attributes, as shown in the following example, which is functionally equivalent:
```python
class EntityWithCategory(Entity):
    category: str

class HealthDatasetItem(DefaultImageDatasetItem):
    objects: list[EntityWithCategory]
    image_type: str
```

### Initialize a DatasetBuilder

#### Use a built-in builder

The Health dataset follows a **folder** structure that can be handled by Pixano:

```
root_folder/
    split1/
        view0.ext
        view1.ext
        ...
        viewN.ext
        metadata.jsonl
    split2/
        ...
```

<!--TODO explain metadata.jsonl, better describe FolderBuilder usage/possibility ?-->

Therefore the `pixano.datasets.builders.ImageFolderBuilder` can be used to construct the Pixano dataset as follows:

```python
from pathlib import Path
from pixano.datasets import DatasetInfo
from pixano.datasets.builders import ImageFolderBuilder


builder = ImageFolderBuilder(
    media_dir=Path("./assets"),
    library_dir=Path("./pixano_library"),
    dataset_item=HealthDatasetItem,
    info=DatasetInfo(
        name="Health Images",
        description="A dataset of health images",
    ),
    dataset_path="/health_images"
)

dataset = builder.build(mode="create")
```

`media_dir` and `library_dir` should be the same you provide to [launch Pixano](https://pixano.github.io/pixano/latest/getting_started/launching_the_app).

#### Write your own builder

While it is convenient to use built-in dataset builders, Pixano do not cover all your use-cases. Fortunatly it is possible to design your own builder by subclassing the `pixano.datasets.builders.DatasetBuilder` class and implementing the `generate_data` method.

Here is roughly the code for a custom `HealthFolderBuilder`. It is a simplified version of FolderBuilder.

```python
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from pixano.datasets.dataset_info import DatasetInfo
from pixano.features import (
    Annotation,
    BaseSchema,
    Entity,
    Image,
    SourceKind,
)


class TestFolderBuilder(ImageFolderBuilder):

    def generate_data(
        self,
    ) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        self.source_id = self.add_source("Builder", SourceKind.OTHER)
        for split in self.source_dir.glob("*"):
            if not split.is_dir() or split.name.startswith("."):
                continue
            try:
                dataset_pieces = self._read_metadata(split / self.METADATA_FILENAME)
            except FileNotFoundError:
                raise ValueError(f"Metadata not found in {str(split)}")

            for i, dataset_piece in enumerate(dataset_pieces):
                # split metadata in different kind
                item_metadata = {}
                view_metadata = {}
                obj_metadata = {}
                for k in dataset_piece.keys():
                    if k in self.views_schema:
                        view_metadata.update({k: dataset_piece.get(k, None)})
                    elif k in self.entities_schema:
                        obj_metadata.update({k: dataset_piece.get(k, None)})
                    else:
                        item_metadata.update({k: dataset_piece.get(k, None)})

                # create item
                item = self._create_item(split.name, **item_metadata)

                # create view
                views_data: list[tuple[str, Image]] = []
                for view_name, im in view_metadata.items():
                    # in case split is or is not in given filename
                    view_file = self.source_dir / Path(im) if split.name == Path(im).parts[0] else split / Path(im)
                    if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                        view = self._create_view(item, view_file, Image)
                        views_data.append((view_name, view))

                # create entities and annotations
                all_entities_data: dict[str, list[Entity]] = defaultdict(list)
                all_annotations_data: dict[str, list[Annotation]] = defaultdict(list)
                for k, v in obj_metadata.items():
                    if k in self.entities_schema and v is not None:
                        entity_name = k
                        raw_entities_data = v
                        entity_schema = self.entities_schema.get(entity_name)
                        if entity_schema is not None:
                            entities_data, annotations_data = self._create_objects_entities(
                                item, views_data, entity_name, entity_schema, raw_entities_data
                            )

                            for name, entities in entities_data.items():
                                all_entities_data[name].extend(entities)

                            for name, annotations in annotations_data.items():
                                all_annotations_data[name].extend(annotations)

                yield {self.item_schema_name: item}
                for view_name, view in views_data:
                    yield {view_name: view}

                if all_entities_data is None:
                    continue

                yield all_entities_data
                yield all_annotations_data


builder = TestFolderBuilder(
    media_dir=media_dir,
    library_dir=library_dir,
    dataset_item=CustomDatasetItem,
    info=DatasetInfo(
        name=dataset_name,
        description=dataset_description
    ),
    dataset_path=dataset_dirname,
)

builder.build(mode="overwrite")
```

We recommend that you take a look at the implementation of the class `pixano.datasets.builders.FolderBaseBuilder` for the complete code to understand how to construct your own builder.

Notice that the `generate_data` is a generator of dictionaries whose keys are the names of the tables to fill and the values one example or a list of `pixano.features.BaseSchema` to fill these tables. The builder flushes data by chunks of a size configured for every table with the argument `flush_every_n_samples` in the `build` method. This offers a trade-off between speed and memory footprint.

## Query your dataset

### Python API

To interact with your dataset you can use CRUD (create, read, update, and delete) operations either on a table level or on a complete dataset item with the following methods:

| operation | table       | dataset item         |
| --------- | ----------- | -------------------- |
| create    | add_data    | add_dataset_items    |
| read      | get_data    | get_dataset_items    |
| update    | update_data | update_dataset_items |
| delete    | delete_data | delete_dataset_items |

Here is an example to read the first two image views:

```python
from pixano.datasets import Dataset

dataset = Dataset( # Load the dataset
    Path("./pixano_library/health_dataset"), media_dir=Path("./assets/")
)

dataset.get_data("image", limit=2, skip=0) # Fetch images

>>> [Image(id='QmmM6LhwB4uMMCRUjgXejY', created_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 364059), updated_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 364059), item_ref=ItemRef(name='item', id='iyA4tHmGeHPP4N6diSuUXi'), parent_ref=ViewRef(name='', id=''), url='/health_images/all/microcope-red_blood_cells.jpg', width=2560, height=1920, format='JPEG'), Image(id='SNgW9Zk68g7mBW2CuHQQKZ', created_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 367359), updated_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 367359), item_ref=ItemRef(name='item', id='VkBcn4bhgt2RRJNWWjvDN5'), parent_ref=ViewRef(name='', id=''), url='/health_images/all/microscope-peau.jpg', width=896, height=550, format='JPEG')]
```

And here is an example to read the dataset item whose id is `'iyA4tHmGeHPP4N6diSuUXi'`. Beware that because they are generated randomly you won't have the same id in your dataset.

```python
dataset.get_dataset_items("iyA4tHmGeHPP4N6diSuUXi")

>>> DatasetItem(id='iyA4tHmGeHPP4N6diSuUXi', split='all', created_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 363831), updated_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 363831), image=Image(id='QmmM6LhwB4uMMCRUjgXejY', created_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 364059), updated_at=datetime.datetime(2024, 11, 7, 10, 14, 5, 364059), item_ref=ItemRef(name='item', id='iyA4tHmGeHPP4N6diSuUXi'), parent_ref=ViewRef(name='', id=''), url='/health_images/all/microcope-red_blood_cells.jpg', width=2560, height=1920, format='JPEG'), objects=[], bbox=[], keypoints=[], image_type='microcope')
```

### REST API

To use the REST API, we first need to launch the Pixano's app.

```bash
pixano ./pixano_library ./assets --host localhost --port 8000
```

Then we can call the endpoints of the REST API. To have the complete list of endpoints, we can have take a look at the Swagger docs [http://localhost:8000/docs](http://localhost:8000/docs) or look at the relevant [documentation](../api_reference/index.md).

To fetch the first two image views here is the call:

```bash
curl -X 'GET' \
  'http://localhost:8000/views/health_images/image/?limit=2&skip=0' \
  -H 'accept: application/json'

>>> [
  {
    "id": "QmmM6LhwB4uMMCRUjgXejY",
    "created_at": "2024-11-07T10:14:05.364059",
    "updated_at": "2024-11-07T10:14:05.364059",
    "table_info": {
      "name": "image",
      "group": "views",
      "base_schema": "Image"
    },
    "data": {
      "item_ref": {
        "name": "item",
        "id": "iyA4tHmGeHPP4N6diSuUXi"
      },
      "parent_ref": {
        "name": "",
        "id": ""
      },
      "url": "/health_images/all/microcope-red_blood_cells.jpg",
      "width": 2560,
      "height": 1920,
      "format": "JPEG"
    }
  },
  {
    "id": "SNgW9Zk68g7mBW2CuHQQKZ",
    "created_at": "2024-11-07T10:14:05.367359",
    "updated_at": "2024-11-07T10:14:05.367359",
    "table_info": {
      "name": "image",
      "group": "views",
      "base_schema": "Image"
    },
    "data": {
      "item_ref": {
        "name": "item",
        "id": "VkBcn4bhgt2RRJNWWjvDN5"
      },
      "parent_ref": {
        "name": "",
        "id": ""
      },
      "url": "/health_images/all/microscope-peau.jpg",
      "width": 896,
      "height": 550,
      "format": "JPEG"
    }
  }
]
```
