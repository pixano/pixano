# Segmentation powered by SAM

## Context

[SAM](https://github.com/facebookresearch/segment-anything) (Segment Anything Model) is an open-source model proposed by Meta to perform mask segmentation from boxes, keypoints and/or original masks.

Pixano's web app integrates SAM to quickly annotate your images. It first requires to pre-compute the embeddings of the images.

This tutorial will help you unlock this feature.

## Create image embeddings for SAM

### Install requirements

1. Pip dependencies

Install the official SAM repo, `onnx` to export the model and `transformers` to get the image embeddings.

```bash
pip install git+https://github.com/facebookresearch/segment-anything.git
pip install onnx transformers
```

2. Download the model and export it to ONNX format.

```bash
git clone https://github.com/facebookresearch/segment-anything.git

cd segment-anything

wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth

python segment-anything/scripts/export_onnx_model.py \
    --checkpoint sam_vit_h_4b8939.pth \
    --model-type vit_h \
    --output sam_h.onnx

cp sam_h.onnx /path/to/pixano/models/
# Defaults is models/ under the library
```

### Create the embeddings

The following suppose the [library tutorial](./create_your_first_library.md) has been followed previously to initialize the library containing the `health_dataset`.

1. Load the model and the dataset.

```python
import torch
from transformers import SamModel, SamProcessor
from pixano.datasets import Dataset
from pixano.features import Image
from pathlib import Path

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SamModel.from_pretrained("facebook/sam-vit-huge").to(device=device)
processor = SamProcessor.from_pretrained("facebook/sam-vit-huge")

dataset = Dataset(
    Path("./pixano_library/health_dataset"),
    media_dir=Path("./assets/")
)

images: list[Image] = dataset.get_data("image", limit=100)
num_images  = len(images)

print(num_images)

>>> 11
```

2. Create the SAM embeddings table.

```python
from pixano.features import ViewEmbedding
from pixano.datasets.dataset_schema import SchemaRelation
from lancedb.pydantic import Vector

class SAMViewEmbedding(ViewEmbedding):
    vector: Vector(1048576)

sam_table = dataset.create_table(
    name="sam_embedding",
    schema=SAMViewEmbedding,
    relation_item=SchemaRelation.ONE_TO_ONE,
    mode="overwrite"
)
```

3. Compute the embeddings

```python
import shortuuid
from pixano.features import ViewRef

embeddings = []
for i, image in enumerate(images):
    pil_image = image.open( # Load the actual image
            media_dir=dataset.media_dir,
            output_type="image"
        ).convert("RGB")
    with torch.inference_mode():
        # Compute the embeddings
        inputs = processor(pil_image, return_tensors="pt").to(device=device)
        output = model.get_image_embeddings(inputs["pixel_values"])
    # Validate the output
    embedding = dataset.schema.schemas["sam_embedding"](
        id=shortuuid.uuid(),
        item_ref=image.item_ref,
        view_ref=ViewRef(id=image.id, name=image.table_name),
        vector=output.flatten().tolist(),
        shape=output.squeeze().shape,
    )
    embeddings.append(embedding)

# Flush to the table
dataset.add_data("sam_embedding", embeddings)
```

### Use the app !

Now you are all set to use SAM, follow the [using the app](../getting_started/using_the_app.md) guide !
