# Pixano Python Data Model

Pixano Data Model consist of extandable Python classes

    "DatasetItem",

    "Image",
    "SequenceFrame",
    *"Video",
    *"PointCloud",

    "ImageObject",
    "TrackObject",

    "Tracklet",

    *"Embedding",

    "BBox",
    "CompressedRLE",
    "KeyPoints",
    *"BBox3D",
    *"KeyPoints3D",

    "NDArrayFloat",
    *"CamCalibration",

    * theses classes are available but not currently supported front side

## DatasetItem

Defined in pixano.datasets

DatasetItem is the main dataset item class, which contains metadata, and also custom fields for different groups of data.

- ITEM: Item
- VIEW: View (chilren: Image, SequenceFrame, Video, PointCloud)
- OBJECT: Object (child: ImageObject, TrackObject)
- TRACKLET: Tracklet
- EMBEDDING: Embedding

```
Item:
    id: str
    split: str
```

When you create a DatasetItem class, each field fall in a group depending on his type.

Item's fields 'id' and 'split' are automatically included in DatasetItem.

If your dataset item contains several instance of a data (in example below, each dataset item contains several sequence frames), you must give a list type

```
class CustomDataItem(DatasetItem):
    sequence_name: str  # <-- this type doesn't extends one of group types, it falls in Item as datasetItem metadata
    nb_frames: int      # <-- idem
    image: list[SequenceFrame]   # <-- this type is a list of SequenceType, it falls in VIEW group
    objects: list[TrackObject]   # <-- this type is a list of TrackObject, it falls in OBJECT group
    tracklets: list[Tracklet]  # <-- this type is a list of Tracklet, it falls in TRACKLET group
```

## VIEW Group classes

Defined in pixano.datasets.features.schemas

```
View(BaseSchema):
    id: str
    item_id: str
```

```
Image(View):
    url: str
    width: int
    height: int
    format: str
```

```
SequenceFrame(Image):
    sequence_id: str
    timestamp: float
    frame_index: int
```

```
Video(View):
    url: str
    num_frames: int
    fps: float
    width: int
    height: int
    format: str
    duration: float
```

```
PointCloud(View):
    url: str
```

## OBJECT Group classes

Defined in pixano.datasets.features.schemas

```
ImageObject:
    id: str
    item_id: str
    view_id: str
    bbox: BBox = BBox.none()
    mask: CompressedRLE = CompressedRLE.none()
    keypoints: KeyPoints = KeyPoints.none()
```

```
TrackObject(ImageObject):
    tracklet_id: str
    is_key: bool
    frame_idx: int
```

## TRACKLET Group classes

Defined in pixano.datasets.features.schemas

Note: Pixano front requires start_timestep and end_timestep. So, we should keep only Tracklet and TrackletWithTimestamp (add start/end_timestep to both)

```
Tracklet:
    id: str
    item_id: str
    track_id: str
    start_timestep: int
    end_timestep: int
    start_timestamp: int
    end_timestamp: int
```

## EMBEDDING Group class

Defined in pixano.datasets.features.schemas

```
Embedding:
    id: str
    item_id: str
```

## Shapes classes

Defined in pixano.datasets.features.types

```
BBox:
    coords: list[float]
    format: str
    is_normalized: bool
    confidence: float
```

```
CompressedRLE:
    size: list[int]
    counts: bytes
```

```
KeyPoints:
    template_id: str
    coords: list[float]
    states: list[str]
```

```
BBox3D:
    position: list[float]
    size: list[float]
    heading: float
```

```
KeyPoints3D:
    template_id: str
    coords: list[float]
    visibles: list[bool]
```

## Misc.

Defined in pixano.datasets.features.types

```
NDArrayFloat:
    values: list[float]
    shape: list[int]
```

```
CamCalibration:
    type (str): type of camera
    base_intrinsics (BaseIntrinsics): base intrinsics
    extrinsics (Extrinsics): extrinsics
    intrinsics (Intrinsics): intrinsics
```
