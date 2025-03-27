# Key concepts

## Context

Pixano is a data-centric tool that provides multiple functionalities:

1. **Dataset management** in a fast, columnar data format based on the [Lance](https://lancedb.github.io/lance/) format and the [LanceDB](https://lancedb.github.io/lancedb/) vector database. The dataset is split into various Lance tables to separate features of each dataset item (metadata, views, entities, annotations, embeddings, sources).
2. **An annotation web platform** powered by AI.

## Pixano Layers

Pixano has **three** layers:

- The **backend** manages datasets from creation to operations like insertions, deletions, updates, and statistical computations.
- The **REST API**, which requires an **app** to be started, handles REST requests (as its name suggests). These requests are translated for the backend to perform one or multiple operations based on the request, and it returns the results.
- The **UI**, which also requires an **app** to be started, allows users to visualize data and interact with it to add, update, or delete annotations and entities.

## Datasets

Datasets are specific [LanceDB](https://lancedb.github.io/lancedb/) databases. They are split into tables storing different types of information. Each dataset contains **features** that have two levels of description:

- **Top-level features**, or **schemas**, which are tables containing comprehensive information on a part of a dataset item, such as a view, an annotation, or an entity.
- **Bottom-level features**, or **types**, which contain atomic information. They can be standard Python types or complex types allowed by LanceDB, which are BaseModels with constraints.

### Schemas

Schemas contain information related to a specific part of an item in dedicated tables. They are defined using the Python API from a `BaseSchema`, which inherits from [LanceModel](https://lancedb.github.io/lancedb/python/python/#lancedb.pydantic.LanceModel).

We strongly suggest reviewing [LanceModel](https://lancedb.github.io/lancedb/python/python/#lancedb.pydantic.LanceModel) before proceeding further.

Since Lance stores data in a columnar format, the `BaseSchema` is structured as follows:

```python
from lancedb.pydantic import LanceModel


class BaseSchema(LanceModel):
    id: str
    created_at: datetime
    updated_at: datetime
```

The **id** must be a unique identifier to retrieve the correct data.

Pixano supports various schema groups (`SchemaGroup`), including:

- `SchemaGroup.ITEM`: the unique schema named `'item'` containing metadata related to each dataset **item**.
- `SchemaGroup.VIEW`: schemas related to the **views** of each dataset item, such as images, videos, or text.
- `SchemaGroup.EMBEDDING`: schemas related to the **embeddings** of one or multiple views of a dataset item or its entities.
- `SchemaGroup.ENTITY`: schemas related to **entities** (or objects) within a dataset item.
- `SchemaGroup.ANNOTATION`: schemas related to **annotations** of the entities in a dataset item.
- `SchemaGroup.SOURCE`: the unique schema named `'source'`, containing **sources** for the dataset.

Each group has a base class that organizes all subclasses, defined by Pixano or users, into their respective groups. These are:

- `Item`
- `View`
- `Embedding`
- `Entity`
- `Annotation`
- `Source`

For example, the `Image` view derives from `View` and stores image-specific information:

```python
from datetime import datetime
from pixano.features import View, ItemRef, ViewRef


class Image(View):
    id: str
    created_at: datetime
    updated_at: datetime
    item_ref: ItemRef
    parent_ref: ViewRef
    url: str
    width: int
    height: int
    format: str
```

To define a new schema, Pixano requires two things:

1. Deriving from `BaseSchema`, preferably from a group base class.
2. Registering the custom schema using the `register_schema` function.

```python
from pixano.features import Entity


class MyEntity(Entity):
    category: str
    metadata_int: int
```

### Types

Types hold atomic information within a schema, forming the **columns** of the table that implements the schema.

Pixano supports native Python types with some extensions, such as datetime. It also supports custom types using [BaseModel](https://docs.pydantic.dev/latest/api/base_model/), but it shares the same limitations as Lance.

For example, `ViewRef` is a custom type that defines a reference to a specific ID in a view table with a specific name, as shown below:

```python
from pydantic import BaseModel


class ViewRef(BaseModel):
    name: str
    id: str
```

Currently, it is not possible to register new types for the app. If you need a new type, please open an [issue](https://github.com/pixano/pixano/issues).

## Library, media and models

Pixano presumes that datasets are all stored in a **library**. The path to this library is passed to the app at launch time to allow it to load this datasets.

It also expects all **media** (images, videos, texts, ...) to be available at a location provided at launch time. This media directory should be used as the parent folder to construct url paths for the views (`Image`, `Video`, ...).

Finally, some functionalities available on the UI such as assisted semantic segmentation by AI might require the use of **models** available in a directory whose location should be provided at launch time.
