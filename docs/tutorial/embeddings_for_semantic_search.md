# Embeddings for Semantic Search

## Context

The Pixano's app support **semantic search** which allows a user to search for a view based on a text content.

To do that Pixano requires that the embeddings of the views are pre-computed with the model used for Semantic search. For now, we rely on the [Embeddings functions](https://lancedb.github.io/lancedb/embeddings/embedding_functions/) from LanceDB.

## Open-clip example

We will go through the process of semantic search based on the Open-clip model.

### Pre-compute the embeddings

First, we need to pre-compute the embeddings using LanceDB and Pixano. We will use the Health Images dataset defined in the [library](./create_your_first_library.md) tutorial.

1. Create the Image View Embedding table:

```python
from pathlib import Path
from pixano.datasets.dataset import Dataset


lancedb_embedding_fn = "open-clip"
table_name = "emb_open-clip"

dataset = Dataset( # Load the dataset
    Path("./pixano_library/health_images"), media_dir=Path("./assets/")
)
embedding_schema = ViewEmbedding.create_schema( # Create the ViewEmbeddingSchema
    embedding_fn=lancedb_embedding_fn, # For LanceDB
    table_name=table_name,
    dataset
)
dataset.create_table( # Create the table
    name=table_name,
    schema=embedding_schema,
    relation_item=SchemaRelation.ONE_TO_ONE, # Only one view per item
    mode="create"
)
```

The `pixano.features.ViewEmbedding`'s method `create_schema` create a schema that contains a LanceDB embedding function compatible with Pixano.

2. Compute the embeddings

To compute the embeddings, Pixano needs to access the references to the views. Then, based on these information, it can use the LanceDB embedding function on the views.

```python
views = dataset.get_data("image", limit=100) # Get all views from the dataset.

data = [] # List of dictionnary of ViewEmbedding's model dump without the vector field.
for view in views:
    data.append(
        {
            "id": shortuuid.uuid(),
            "item_ref": {
                "id": view.item_ref.id,
                "name": view.item_ref.name,
            },
            "view_ref": {
                "id": view.id,
                "name": "image",
            },
        }
    )
dataset.compute_view_embeddings(table_name=table_name, data=data)
```
