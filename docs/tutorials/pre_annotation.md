# Pre Annotation

## Context

It is common to use a object detection model to pre-annotate a dataset.

This tutorial will help you unlock this feature.

## Using YOLOv11 from Ultralytics

In your environnement, install [ultralytics](https://www.ultralytics.com)
```bash
pip install ultralytics
```

Set your paths

```python
from pathlib import Path

library = Path("/path_to_pixano_library_dir")
media = Path("/path_to_pixano_media_dir")
dataset_dirname = "pixano_dataset_directory_name"  # as in library directory
```

Utility function to create pixano BBox and associated Entity.

It assume your dataset has been created with the EntityWithCategory custom Entity, and one of the Default provided in `pixano.datasets.workspace`.

Of course you can customize it to match your own dataset.

```python
from pixano.features import BBox, Entity
import shortuuid

class EntityWithCategory(Entity):
    category: str

def create_pixano_bbox_entity(pix_image, bbox_coords, score, category):
    view_ref = {"id": pix_image.id, "name": "image"}
    entity = EntityWithCategory(
        id=shortuuid.uuid(),
        item_ref=pix_image.item_ref,
        view_ref=view_ref,
        category=category,
    )
    bbox = BBox(
        id=shortuuid.uuid(),
        item_ref=pix_image.item_ref,
        view_ref=view_ref,
        entity_ref={"id": entity.id, "name": "objects"},
        confidence=score,
        coords=bbox_coords,
        is_normalized=True,
        format="xyxy",
        # "source_ref": ## if you registered a model source, you can add it here, else it's a default
    )

    return entity, bbox
```

Load YOLOv11 model.

```python
from ultralytics import YOLO

# Load a COCO-pretrained YOLO11n model
model = YOLO("yolo11n.pt")
```

Load your Pixano dataset

```python
from pixano.datasets import Dataset
ds = Dataset(library / dataset_dirname, media_dir=media)
```

Pre-annotate

```python
from tqdm.auto import tqdm

new_entities = []
new_bboxes = []

images = ds.get_data("image")

for image in tqdm(images):
    results = model.predict(media / image.url, verbose=False)
    for res in results:
        for bbox, score, category in zip(
            res.boxes.xyxyn.tolist(),
            res.boxes.conf.tolist(),
            res.boxes.cls.tolist(),
        ):
            entity, pix_bbox = create_pixano_bbox_entity(image, bbox, score, res.names[category])
            new_entities.append(entity)
            new_bboxes.append(pix_bbox)

ds.add_data("objects", new_entities)
ds.add_data("bboxes", new_bboxes)

print("Done")
```

## Using Grounding DINO from IDEA-Research with Pixano Inference

We can use Pixano Inference client as a convenient way to access models, as long as they have a registered inference provider supported by Pixano Inference.

Set your paths

```python
from pathlib import Path

library = Path("/path_to_pixano_library_dir")
media = Path("/path_to_pixano_media_dir")
dataset_dirname = "pixano_dataset_directory_name"  # as in library directory
```

Utility function to create pixano BBox and associated Entity.

It assume your dataset has been created with the EntityWithCategory custom Entity, and one of the Default provided in `pixano.datasets.workspace`.

Of course you can customize it to match your own dataset.

This is exactly the same function as in the previous sample, except for BBox `is_normalized` field, to match Grounding DINO output.

```python
from pixano.features import BBox, Entity
import shortuuid

class EntityWithCategory(Entity):
    category: str

def create_pixano_bbox_entity(pix_image, bbox_coords, score, category):
    view_ref = {"id": pix_image.id, "name": "image"}
    entity = EntityWithCategory(
        id=shortuuid.uuid(),
        item_ref=pix_image.item_ref,
        view_ref=view_ref,
        category=category,
    )
    bbox = BBox(
        id=shortuuid.uuid(),
        item_ref=pix_image.item_ref,
        view_ref=view_ref,
        entity_ref={"id": entity.id, "name": "objects"},
        confidence=score,
        coords=bbox_coords,
        is_normalized=False,
        format="xyxy",
        # "source_ref": ## if you registered a model source, you can add it here, else it's a default
    )

    return entity, bbox
```

Load Grounding DINO model with Pixano Inference from transformers provider ([HuggingFace](https://huggingface.co))

```python
from pixano_inference.providers.transformers import TransformersProvider
from pixano_inference.tasks import ImageTask
import torch

provider = TransformersProvider()
model = provider.load_model(
    "dino",
    ImageTask.ZERO_SHOT_DETECTION.value,
    torch.device("cuda") if torch.cuda.is_available() else "cpu",
    "IDEA-Research/grounding-dino-base"
)
```

Load your Pixano dataset

```python
from pixano.datasets import Dataset
ds = Dataset(library / dataset_dirname, media_dir=media)
```

Pre-annotate. We ask Grounding DINO to detect objects of classes ["person", "car", "motorcycle"].

```python
from pixano_inference.pydantic import ImageZeroShotDetectionOutput
from pixano_inference.utils.media import convert_string_to_image
from tqdm.auto import tqdm

new_entities = []
new_bboxes = []

images = ds.get_data("image")

for image in tqdm(images):
    image_zero_shot_detection_out: ImageZeroShotDetectionOutput = (
        model.image_zero_shot_detection(
            image=convert_string_to_image(media / image.url),
            classes=["person", "car", "motorcycle"],
            box_threshold=0.3,
            text_threshold=0.2,
        )
    )
    for bbox, score, category in zip(
        image_zero_shot_detection_out.boxes,
        image_zero_shot_detection_out.scores,
        image_zero_shot_detection_out.classes,
    ):
        entity, pix_bbox = create_pixano_bbox_entity(image, bbox, score, category)
        new_entities.append(entity)
        new_bboxes.append(pix_bbox)

ds.add_data("objects", new_entities)
ds.add_data("bboxes", new_bboxes)

print("Done")
```
