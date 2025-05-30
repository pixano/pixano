# Semantic search

## Context

The Pixano's app support **semantic search** which allows a user to search for a view based on a text content.

To do that, Pixano requires that the embeddings of the views are pre-computed with the model used for semantic search, using the [embeddings functions](https://lancedb.github.io/lancedb/embeddings/embedding_functions/) from LanceDB.

In this tutorial, we will go through the process of semantic search using the OpenCLIP model.

## Pre-compute the embeddings

First, we need to pre-compute the embeddings using LanceDB and Pixano. We will use the Health Images dataset defined in the [Build and query a dataset](./dataset.md) tutorial.

1. Install OpenCLIP

For this tutorial, we will use OpenCLIP embedding function and therefore need it to be installed.

```bash
pip install open-clip-torch
```

2. Create the Image View Embedding table:

```python
from pathlib import Path
from pixano.datasets import Dataset
from pixano.datasets.dataset_schema import SchemaRelation
from pixano.features import ViewEmbedding

lancedb_embedding_fn = "open-clip"
table_name = "emb_open-clip"

dataset = Dataset( # Load the dataset
    Path("./pixano_library/health_dataset"), media_dir=Path("./assets/")
)
embedding_schema = ViewEmbedding.create_schema( # Create the ViewEmbeddingSchema
    embedding_fn=lancedb_embedding_fn, # For LanceDB
    table_name=table_name,
    dataset=dataset
)
dataset.create_table( # Create the table
    name=table_name,
    schema=embedding_schema,
    relation_item=SchemaRelation.ONE_TO_ONE, # Only one view per item
    mode="create"
)

>>> LanceTable(connection=LanceDBConnection(.../pixano/docs/tutorials/pixano_library/health_dataset/db), name="emb_open-clip")
```

The `pixano.features.ViewEmbedding`'s method `create_schema` create a schema that contains a LanceDB embedding function compatible with Pixano.

3. Compute the embeddings

To compute the embeddings, Pixano needs to access the references to the views. Then, based on these information, it can use the LanceDB embedding function on the views.

```python
import shortuuid
from datetime import datetime

views = dataset.get_data(table_name="image") # Get all views from the dataset's table "image".

data = [] # List of dictionnary of ViewEmbedding's model dump without the vector field.
for view in views:
    data.append(
        {
            "id": shortuuid.uuid(),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "item_ref": {
                "id": view.item_ref.id,
                "name": view.item_ref.name,
            },
            "view_ref": { # Reference to the table "image"
                "id": view.id,
                "name": "image",
            },
        }
    )

dataset.compute_view_embeddings(table_name=table_name, data=data)
```

## Use the semantic search

### With the app

Now you are all set to use the semantic search, follow the [using the app](../getting_started/using_the_app.md) guide!

The semantic search bar will appear on the dataset page.

### With the API

#### Python API

To perform semantic search, simply call the dataset's `semantic_search` method with the text query. It will return the items with the closest view semantically to the query and the distance.

```python
query = "microscope"

dataset.semantic_search(query, table_name, limit=5, skip=0)

>>>(
    [
        Item(id='bFPEPGYaSmJGPakiaPctfF', ..., split='all', image_type='microscope'),
        Item(id='VkBcn4bhgt2RRJNWWjvDN5', ..., split='all', image_type='microscope'),
        Item(id='5XFPk5qwFL5xWhLHzGXLeV', ..., split='all', image_type='microscope'),
        Item(id='A7BXLwmXWRAypbqxd5KqzK', ..., split='all', image_type='peau'),
        Item(id='iyA4tHmGeHPP4N6diSuUXi', ..., split='all', image_type='microcope')
    ],
    [1.5589371919631958, 1.5611850023269653, 1.5707159042358398, 1.5987659692764282, 1.605470895767212]
)
```

#### REST API

You first need to launch the Pixano's app to interact with the REST API.

Then you can curl the REST API to navigate through your items:

```bash
curl -X 'GET' \
  'http://localhost:8000/browser/health_images?limit=5&skip=0&query=microscope&embedding_table=emb_open-clip' \
  -H 'accept: application/json'

>>> {
  "id": "health_images",
  "name": "Health Images",
  "table_data": {
    "columns": [
      {
        "name": "image",
        "type": "image"
      },
      {
        "name": "id",
        "type": "str"
      },
      {
        "name": "created_at",
        "type": "datetime"
      },
      {
        "name": "updated_at",
        "type": "datetime"
      },
      {
        "name": "split",
        "type": "str"
      },
      {
        "name": "image_type",
        "type": "str"
      },
      {
        "name": "distance",
        "type": "float"
      }
    ],
    "rows": [
      {
        "image": "",
        "id": "bFPEPGYaSmJGPakiaPctfF",
        "created_at": "2024-11-07T10:14:05.396010",
        "updated_at": "2024-11-07T10:14:05.396010",
        "split": "all",
        "image_type": "microscope",
        "distance": 1.5589371919631958
      },
      {
        "image": "",
        "id": "VkBcn4bhgt2RRJNWWjvDN5",
        "created_at": "2024-11-07T10:14:05.367159",
        "updated_at": "2024-11-07T10:14:05.367159",
        "split": "all",
        "image_type": "microscope",
        "distance": 1.5611850023269653
      },
      {
        "image": "",
        "id": "5XFPk5qwFL5xWhLHzGXLeV",
        "created_at": "2024-11-07T10:14:05.402816",
        "updated_at": "2024-11-07T10:14:05.402816",
        "split": "all",
        "image_type": "microscope",
        "distance": 1.5707159042358398
      },
      {
        "image": "",
        "id": "A7BXLwmXWRAypbqxd5KqzK",
        "created_at": "2024-11-07T10:14:05.409434",
        "updated_at": "2024-11-07T10:14:05.409434",
        "split": "all",
        "image_type": "peau",
        "distance": 1.5987659692764282
      },
      {
        "image": "",
        "id": "iyA4tHmGeHPP4N6diSuUXi",
        "created_at": "2024-11-07T10:14:05.363831",
        "updated_at": "2024-11-07T10:14:05.363831",
        "split": "all",
        "image_type": "microcope",
        "distance": 1.605470895767212
      }
    ]
  },
  "pagination": {
    "current_page": 0,
    "page_size": 5,
    "total_size": 11
  },
  "semantic_search": [
    "emb_open-clip"
  ]
}
```
