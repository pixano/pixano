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
- `bbox`: the bounding boxes of an item.
- `keypoints`: the keypoints of an item.

This is how it can be defined in code:

```python
from pixano.datasets import DatasetItem
from pixano.features import BBox, Entity, Image, KeyPoints


class EntityWithCategory(Entity):
    category: str


class HealthDatasetItem(DatasetItem):
    image: Image
    objects: list[EntityWithCategory]
    bbox: list[BBox]
    keypoints: list[KeyPoints]
    image_type: str
```

Notice that when multiple elements are attached to an item we use the `list` type.

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

Therefore the `pixano.datasets.builders.ImageFolderBuilder` can be used to construct the Pixano dataset as follows:

```python
from pathlib import Path
from pixano.datasets import DatasetInfo
from pixano.datasets.builders import ImageFolderBuilder


builder = ImageFolderBuilder(
    source_dir=Path("./assets/health_images"),
    target_dir=Path("./pixano_library/health_images"),
    dataset_item=HealthDatasetItem,
    info=DatasetInfo(
        id="health_images",
        name="Health Images",
        description="A dataset of health images",
    ),
    url_prefix="/health_images"
    # By default, the images' URLs are relative to the health_images folder.
    # We assume Pixano will be launched with the "assets/" directory as media_dir.
)

dataset = builder.build(mode="create")
```

#### Write your own builder

While it is convenient to use built-in dataset builders, Pixano do not cover all your use-cases. Fortunatly it is possible to design your own builder by subclassing the `pixano.datasets.builders.DatasetBuilder` class and implementing the `generate_data` method.

Here is roughly the code for the `ImageFolderBuilder`:

```python
from pixano.datasets.builders import DatasetBuilder
from pixano.features import BaseSchema

class ImageFolderBuilder(DatasetBuilder):
    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        dataset_item: type[DatasetItem],
        info: DatasetInfo,
        url_prefix: str,
    ) -> None:
        super().__init__(target_dir=target_dir, dataset_item=dataset_item, info=info)
        self.source_dir = Path(source_dir)
        self.url_prefix = url_prefix

        self.view_name = "image"
        self.view_schema: type[View] = Image
        self.entity_name = objects
        self.entity_schema: type[Entity] = EntityWithCategory

    def generate_data(
        self,
    ) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        source_id = None
        for split in self.source_dir.glob("*"):
            if split.is_dir() and not split.name.startswith("."):
                metadata = self._read_metadata(split / "metadata.jsonl")

                for view_file in split.glob("*"):
                    # only consider {split}/{item}.{ext} files
                    if view_file.is_file() and view_file.suffix in self.EXTENSIONS:
                        # retrieve item metadata in metadata file
                        item_metadata = {}
                        for m in metadata:
                            if m[self.view_name] == view_file.name:
                                item_metadata = m
                                break
                        if not item_metadata:
                            raise ValueError(f"Metadata not found for {view_file}")

                        # extract entity metadata from item metadata
                        entities_data = item_metadata.pop(self.entity_name, None)

                        # create item
                        item = self._create_item(split.name, **item_metadata)

                        # create view
                        view = self._create_view(item, view_file, self.view_schema)

                        if entities_data is None:
                            yield {
                                self.item_schema_name: item,
                                self.view_name: view,
                            }
                            continue
                        elif source_id is None:
                            source_id = self.add_source("Builder", SourceKind.OTHER)

                        # create entities and their annotations
                        entities, annotations = self._create_entities(item, view, entities_data, source_id)

                        yield {
                            self.item_schema_name: item,
                            self.view_name: view,
                            self.entity_name: entities,
                            **annotations,
                        }

builder = ImageFolderBuilder(
    source_dir=Path("./assets/health_images"),
    target_dir=Path("./pixano_library/health_images"),
    dataset_item=HealthDatasetItem,
    info=DatasetInfo(
        id="health_images",
        name="Health Images",
        description="A dataset of health images",
    ),
    url_prefix="/health_images"
    # By default, the images' URLs are relative to the health_images folder.
    # We assume Pixano will be launched with the "assets/" directory as media_dir.
)

dataset = builder.build(mode="create")
```

We recommend that you take a look at the implementation of the class `pixano.datasets.builders.FolderBaseBuilder` for the complete code to understand how to construct your own builder.

Notice that the output of the `generate_data` consists in a dictionary whose keys are the names of the tables to fill and the values one example or a list of `pixano.features.BaseSchema` to fill these tables.

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
dataset.get_data("image", limit=2, skip=0)

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
