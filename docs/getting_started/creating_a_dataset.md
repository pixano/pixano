# Creating a dataset

## Defining a dataset

A dataset is a collection of tables from different `SchemaGroup`s. To generate this collection, you provide a `DatasetItem`, which is essentially a [BaseModel](https://docs.pydantic.dev/latest/api/base_model/). The attributes of this DatasetItem must be features (see our [key concepts](./key_concepts.md) page) and are organized as follows:

- **Schemas** are stored in their respective tables.
- **Types** are stored in the `'item'` table.

Features can be a single element or a list.

Example:

```python
from pixano.features import BBox, Classification, Entity, Image, Text
from pixano.datasets import DatasetItem


class MyEntity(Entity):
    category: str
    metadata_int: int


class MyDatasetItem(DatasetItem):
    item_metadata: str # will be stored in table 'item'
    image: Image # will be stored in table 'image'
    texts: list[Text] # will be stored in table 'texts'
    image_entities: list[MyEntity] # will be stored in table 'image_entities'
    bboxes: list[BBox] # will be stored in table 'bboxes'
    text_entities: list[Entity] # will be stored in table 'text_entities'
    text_classifs: list[Classification] # will be stored in table 'text_classifs'
```

## Building a dataset

To build the dataset, Pixano provides a generic class `DatasetBuilder` and specific classes detailed in the [api reference](../api_reference/index.md).

To construct a dataset builder, derive from `DatasetBuilder` to properly handle your data and implement the `generate_data` method. This method returns an iterator of dictionnary whose keys are table_names and values one `BaseSchema` or a list of `BaseSchema` to insert into that table.

```python
from pixano.datasets.builders import DatasetBuilder


info = DatasetInfo(
    name="My super dataset",
    description="This dataset tracks reference to super stuff."
)

class MyDatasetBuilder(DatasetBuilder):
    def __init__(
        target_dir: Path | str,
    ):
        super().__init__(
            target_dir=target_dir,
            schemas=MyDatasetItem,
            info=info
        )

    def generate_data() -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        ...

        return {
            "item": ...,
            "bboxes": ...,
            ...
        }
```

For more detailed information, check our tutorial on [how to build and query a dataset](../tutorials/dataset.md).
