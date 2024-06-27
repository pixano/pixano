# Pixano Python Data Model

Pixano Data Model consist of extandable Python classes


    "DatasetItem",

    "Image",
    "SequenceFrame",
    *"Video",
    *"PointCloud",

    "Object",
    "TrackObject",

    "Tracklet",
    "TrackletWithTimestamp",
    "TrackletWithTimestep",
    "TrackletWithTimestepAndTimestamp",

    "BBox",
    "CompressedRLE",
    "KeyPoints",
    *"BBox3D",
    *"KeyPoints3D",

    "NDArrayFloat",
    *"Embedding",
    *"CamCalibration",

    * theses classes are available but not currently supported front side




## DatasetItem

Defined in pixano.datasets


## Vision classes
Defined in pixano.datasets.features.schemas

```
Image:
    id: str
    item_id: str
    url: str
    width: int
    height: int
    format: str
```
```
SequenceFrame:
    id: str
    item_id: str
    url: str
    width: int
    height: int
    format: str
    sequence_id: str
    timestamp: float
    frame_index: int
```
```
Video:
    id: str
    item_id: str
    url: str
    num_frames: int
    fps: float
    width: int
    height: int
    format: str
    duration: float
```
```
PointCloud:
    id: str
    item_id: str
    url: str
```

## Objects classes
Defined in pixano.datasets.features.schemas

```
Object:
    id: str
    item_id: str
    view_id: str
    bbox: BBox = BBox.none()
    mask: CompressedRLE = CompressedRLE.none()
    keypoints: KeyPoints = KeyPoints.none()
```

```
TrackObject:
    id: str
    item_id: str
    view_id: str
    bbox: BBox = BBox.none()
    mask: CompressedRLE = CompressedRLE.none()
    keypoints: KeyPoints = KeyPoints.none()
    tracklet_id: str
    is_key: bool
    frame_idx: int
```


## Tracklets classes
Defined in pixano.datasets.features.schemas

Note: We need start_timestep and end_timestep
So, we should keep only Tracklet and TrackletWithTimestamp ((add start/end_timestep to both)

```
Tracklet:
    id: str
    item_id: str
    track_id: str
```
```
TrackletWithTimestamp:
    id: str
    item_id: str
    track_id: str
    start_timestamp: int
    end_timestamp: int
```
```
TrackletWithTimestep:
    id: str
    item_id: str
    track_id: str
    start_timestep: int
    end_timestep: int
```
```
TrackletWithTimestepAndTimestamp:
    id: str
    item_id: str
    track_id: str
    start_timestep: int
    end_timestep: int
    start_timestamp: int
    end_timestamp: int
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
    states: list[str]  # replace by features: list[dict] ?
```
```
BBox3D:
    position: list[float]
    size: list[float]
    heading: float  # TODO : use list[float] instead (need to adapt VDP dataset)
```
```
KeyPoints3D:
    template_id: str
    coords: list[float]
    visibles: list[bool]   # replace by features: list[dict] ?
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

Defined in pixano.datasets.features.schemas
```
Embedding:
    id: str
    item_id: str
```
