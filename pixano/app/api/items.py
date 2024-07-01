# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from collections import defaultdict

# TMP legacy
from typing import Annotated, Optional

import pyarrow as pa
import shortuuid
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params
from pydantic import BaseModel

import pixano.datasets.dataset_explorer as de
from pixano.app.settings import Settings, get_settings
from pixano.datasets import Dataset, DatasetItem
from pixano.datasets.features import (
    BBox,
    CompressedRLE,
    Image,
    KeyPoints,
    SequenceFrame,
)
from pixano.datasets.features.schemas.group import _SchemaGroup
from pixano.datasets.utils import image as image_utils


class FrontDatasetItem(BaseModel):
    """Front format DatasetItem."""

    id: str
    datasetId: str
    type: str
    split: str
    features: Optional[dict] = None
    views: Optional[dict] = None
    objects: Optional[list] = None
    embeddings: Optional[dict] = None


router = APIRouter(tags=["items"], prefix="/datasets/{ds_id}")


@router.get("/item_ids", response_model=list[str])
async def get_dataset_item_ids(
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """## Get all dataset items ids.

    Args:
        ds_id (str): dataset id
        settings(Settings): settings

    Returns:
        list[str]: all items id
    """

    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        all_ids = sorted(dataset.get_all_ids())
        return all_ids
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.get("/explorer", response_model=de.DatasetExplorer)
async def get_dataset_explorer(  # noqa: D417
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    params: Params = Depends(),
) -> de.DatasetExplorer:  # type: ignore
    """## Load dataset items.

    Args:

        ds_id (str): Dataset ID

        params (Params, optional): Pagination parameters (offset and limit). Defaults to Depends().

    Returns:
        Page[DatasetExplorer]: Dataset explorer page
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        # Get page parameters
        params = resolve_params(params)
        raw_params = params.to_raw_params()
        total = dataset.num_rows

        # Check page parameters
        start = raw_params.offset
        stop = min(raw_params.offset + raw_params.limit, total)
        if start >= stop:
            raise HTTPException(
                status_code=404,
                detail=f"Invalid page parameters (start {start}, stop {stop})",
            )

        # Load dataset items
        all_ids = dataset.get_all_ids()
        ids = sorted(all_ids)[raw_params.offset : raw_params.offset + raw_params.limit]
        items = dataset.read_items(
            ids
        )  # future API: will get only relevant info (ex:  we don't need objects, all frames, etc..)
        if items:
            # convert CustomDatasetItem (from new API) to TableData
            # build ColDesc
            groups = defaultdict(list)
            for tname in vars(items[0]).keys():
                found_group = (
                    _SchemaGroup.ITEM
                )  # if no matching group (-> it's not a table name), it is in ITEM
                for group, tnames in dataset.dataset_schema._groups.items():
                    if tname in tnames:
                        found_group = group
                        break
                groups[found_group].append(tname)
            cols = []
            for feat in groups[_SchemaGroup.VIEW]:
                view_item = getattr(items[0], feat)
                if isinstance(view_item, Image):
                    view_type = "image"
                elif (
                    isinstance(view_item, list)
                    and len(view_item) > 0
                    and isinstance(view_item[0], SequenceFrame)
                ):
                    # TMP (video previews are not generated yet
                    # so we put an image for now ("video"  # or "sequenceframe" ?)
                    view_type = "image"
                else:
                    print("ERROR: unknown view type", type(view_item), view_item)
                    view_type = type(view_item).__name__
                cols.append(de.ColDesc(name=feat, type=view_type))
            for feat in groups[_SchemaGroup.ITEM]:
                cols.append(
                    de.ColDesc(name=feat, type=type(getattr(items[0], feat)).__name__)
                )

            # build rows
            rows = []
            for item in items:
                row = {}
                # VIEWS -> thumbnails previews
                for feat in groups[_SchemaGroup.VIEW]:
                    view_item = getattr(item, feat)
                    if isinstance(view_item, Image):
                        row[feat] = view_item.open(dataset.path / "media")
                    elif (
                        isinstance(view_item, list)
                        and len(view_item) > 0
                        and isinstance(view_item[0], SequenceFrame)
                    ):
                        row[feat] = view_item[0].open(dataset.path / "media")
                # ITEM features
                for feat in groups[_SchemaGroup.ITEM]:
                    row[feat] = getattr(item, feat)

                rows.append(row)

            # Return dataset items
            return de.DatasetExplorer(
                id=ds_id,
                name=dataset.info.name,
                table_data=de.TableData(cols=cols, rows=rows),
                pagination=de.PaginationInfo(
                    current=start, size=raw_params.limit, total=total
                ),
                sem_search=[],
            )
        raise HTTPException(
            status_code=404,
            detail=(
                f"No items found with page parameters (start {start}, "
                f"stop {stop}) in dataset",
            ),
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.post("/search", response_model=Page[DatasetItem])
async def search_dataset_items(  # noqa: D417
    ds_id: str,
    query: dict[str, str],
    settings: Annotated[Settings, Depends(get_settings)],
    params: Params = Depends(),
) -> Page[DatasetItem]:  # type: ignore
    """Load dataset items with a query.

    Args:
        ds_id (str): Dataset ID
        query (dict[str, str]): Search query
        params (Params, optional): Pagination parameters (offset and limit).
            Defaults to Depends().

    Returns:
        Page[DatasetItem]: Dataset items page
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        # Get page parameters
        params = resolve_params(params)
        raw_params = params.to_raw_params()
        total = dataset.num_rows

        # Check page parameters
        start = raw_params.offset
        stop = min(raw_params.offset + raw_params.limit, total)
        if start >= stop:
            raise HTTPException(status_code=404, detail="Invalid page parameters")

        # Load dataset items
        items = dataset.search_items(raw_params.limit, raw_params.offset, query)

        # Return dataset items
        if items:
            return create_page(items, total=total, params=params)
        raise HTTPException(
            status_code=404, detail=f"No items found for query '{query}' in dataset"
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.get("/items/{item_id}", response_model=FrontDatasetItem)
async def get_dataset_item(  # noqa: D417
    ds_id: str,
    item_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FrontDatasetItem:  # type: ignore
    """Load dataset item.

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID

    Returns:
        DatasetItem: Dataset item
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
        )

    # Load dataset item
    item = dataset.read_item(item_id)

    groups = defaultdict(list)
    for tname in vars(item).keys():
        found_group = (
            _SchemaGroup.ITEM
        )  # if no matching group (-> it's not a table name), it is in ITEM
        for group, tnames in dataset.dataset_schema._groups.items():
            if tname in tnames:
                found_group = group
                break
        if tname not in [
            "id",
            "split",
        ]:  # id and split are always present, and in ITEM group
            groups[found_group].append(tname)

    # features
    features = {
        feat: {
            "name": feat,
            "dtype": type(getattr(item, feat)).__name__,
            "value": getattr(item, feat),
        }
        for feat in groups[_SchemaGroup.ITEM]
    }

    # views : {"table_name": ItemView}
    views = {}
    view_type = "image"
    for view_name in groups[_SchemaGroup.VIEW]:
        view_item = getattr(item, view_name)
        if (
            isinstance(view_item, list)
            and len(view_item) > 0
            and isinstance(view_item[0], SequenceFrame)
        ):
            views[view_name] = sorted(
                [
                    {
                        "id": frame.id,
                        "type": "image",  # note: it's an image frame from a video
                        "frame_index": frame.frame_index,
                        "uri": "data/" + dataset.path.name + "/media/" + frame.url,
                        # "uri": view_item[0].open(dataset.path / "media"),  # TMP!! need to give vid..?
                        "thumbnail": None,  # frame.open(dataset.path / "media"),
                        "features": {
                            "width": {
                                "name": "width",
                                "dtype": "int",
                                "value": frame.width,
                            },
                            "height": {
                                "name": "height",
                                "dtype": "int",
                                "value": frame.height,
                            },
                        },
                    }
                    for frame in view_item
                ],
                key=lambda x: x["frame_index"],
            )
            view_type = "video"
        elif isinstance(view_item, Image):
            views[view_name] = {
                "id": view_item.id,
                "type": "image",
                "uri": "data/" + dataset.path.name + "/media/" + view_item.url,
                "thumbnail": None,  # view_item.open(dataset.path / "media"),
                "features": {
                    "width": {
                        "name": "width",
                        "dtype": "int",
                        "value": view_item.width,
                    },
                    "height": {
                        "name": "height",
                        "dtype": "int",
                        "value": view_item.height,
                    },
                },
            }

    # objects
    # TMP NOTE : the objects contents may still be subject to change -- WIP
    objects = []
    NoneBBox = BBox.none()
    NoneMask = CompressedRLE.none()
    NoneKeypoints = KeyPoints.none()
    if view_type == "image":
        for obj_group in groups[_SchemaGroup.OBJECT]:
            objects.extend(
                [
                    {
                        "id": obj.id,
                        "datasetItemType": view_type,
                        "item_id": item_id,
                        "source_id": "Ground Truth",  # ??
                        "view_id": obj.view_id,
                        "features": {
                            fname: {
                                "name": fname,
                                "dtype": type(getattr(obj, fname)).__name__,
                                "value": getattr(obj, fname),
                            }
                            for fname in vars(obj).keys()
                            if fname
                            not in [
                                "id",
                                "item_id",
                                "source_id",
                                "view_id",
                                "bbox",
                                "mask",
                                "keypoints",
                            ]
                        },
                        "bbox": (
                            obj.bbox.to_xywh()
                            if hasattr(obj, "bbox")
                            and obj.bbox != NoneBBox
                            and obj.bbox.coords != []
                            else None
                        ),
                        "mask": (
                            image_utils.rle_to_urle(
                                {"size": obj.mask.size, "counts": obj.mask.counts}
                            )
                            if hasattr(obj, "mask")
                            and obj.mask != NoneMask
                            and len(obj.mask.size) == 2
                            else None
                        ),
                        "keypoints": (
                            {
                                "template_id": obj.keypoints.template_id,
                                "vertices": obj.keypoints.map_back2front_vertices(),
                            }
                            if hasattr(obj, "keypoints")
                            and obj.keypoints != NoneKeypoints
                            and obj.keypoints.coords != []
                            else None
                        ),
                    }
                    for obj in getattr(item, obj_group)
                ]
            )
    else:  # video
        boxes = defaultdict(list)
        keypoints = defaultdict(list)
        tracklet_objs = {}
        tracks = defaultdict(list)

        for tracklet_group in groups[_SchemaGroup.TRACKLET]:
            for tracklet in getattr(item, tracklet_group):

                # gather objects by tracklets
                tracklet_objs[tracklet.id] = [
                    obj
                    for obj_group in groups[_SchemaGroup.OBJECT]
                    for obj in getattr(item, obj_group)
                    if obj.tracklet_id == tracklet.id
                ]
                boxes[tracklet.track_id].extend(
                    [
                        {
                            **vars(obj.bbox.to_xywh()),
                            "frame_index": obj.frame_idx,
                            "is_key": obj.is_key,
                            "is_thumbnail": i == 0,
                            "tracklet_id": tracklet.id,
                        }
                        for i, obj in enumerate(
                            [
                                x
                                for x in tracklet_objs[tracklet.id]
                                if hasattr(x, "bbox")
                                and x.bbox != NoneBBox
                                and x.bbox.coords != []
                            ]
                        )
                    ]
                )
                keypoints[tracklet.track_id].extend(
                    [
                        {
                            "template_id": obj.keypoints.template_id,
                            "vertices": obj.keypoints.map_back2front_vertices(),
                            "frame_index": obj.frame_idx,
                            "is_key": obj.is_key,
                            "is_thumbnail": i == 0,
                            "tracklet_id": tracklet.id,
                        }
                        for i, obj in enumerate(
                            [
                                x
                                for x in tracklet_objs[tracklet.id]
                                if hasattr(x, "keypoints")
                                and x.keypoints != NoneKeypoints
                                and x.keypoints.coords != []
                            ]
                        )
                    ]
                )

                # organize tracklets by tracks
                tracks[tracklet.track_id].append(tracklet)

        for track_id, tracklets in tracks.items():

            # features are taken from first tracklet of each track
            track_feats = tracklets[0]

            # view_id is taken from first object in the first tracklet
            try:
                view_id = next(x.view_id for x in tracklet_objs[tracklets[0].id])
            except StopIteration:
                print(
                    f"ERROR: Error in data: cannot find any object for tracklet {tracklets[0].id} - track skipped"
                )
                continue

            objects.append(
                {
                    "id": track_id,
                    "datasetItemType": view_type,
                    "item_id": item_id,
                    "source_id": "Ground Truth",  # ?? must ensure source
                    "view_id": view_id,
                    "features": {
                        fname: {
                            "name": fname,
                            "dtype": type(getattr(track_feats, fname)).__name__,
                            "value": getattr(track_feats, fname),
                        }
                        for fname in vars(track_feats).keys()
                        if fname
                        not in [
                            "id",
                            "item_id",
                            "track_id",
                            "start_timestamp",
                            "end_timestamp",
                            "start_timestep",
                            "end_timestep",
                            "is_key",  # ??
                        ]  # TODO: define list of unwanted tracklet features
                    },
                    "track": [
                        {
                            "id": tracklet.id,
                            "start": (
                                tracklet.start_timestep
                                if hasattr(tracklet, "start_timestep")
                                else tracklet.start_timestamp
                            ),
                            "end": (
                                tracklet.end_timestep
                                if hasattr(tracklet, "end_timestep")
                                else tracklet.end_timestamp
                            ),
                        }
                        for tracklet in tracklets
                    ],
                    "boxes": boxes[track_id],
                    "keypoints": keypoints[track_id],
                }
            )

    front_item = FrontDatasetItem(
        id=item.id,
        type=view_type,
        datasetId=ds_id,
        split=item.split,
        views=views,
        objects=objects,
        features=features,
        embeddings={},  # TODO
    )

    # print(front_item)

    # Return dataset item
    if front_item:
        return front_item
    raise HTTPException(
        status_code=404,
        detail=f"Item '{item_id}' not found in dataset",
    )


@router.post("/items/{item_id}", response_model=FrontDatasetItem)
async def post_dataset_item(  # noqa: D417
    ds_id: str,
    item: FrontDatasetItem,  # type: ignore
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Save dataset item.

    Args:
        ds_id (str): Dataset ID
        item (FrontDatasetItem): Item to save
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
        )

    # Local utility function to convert objects to pyarrow format
    # also adapt features to table format
    def convert_objects_to_pyarrow(table, objs):
        # Convert objects to PyArrow
        # adapt features
        for obj in objs:
            if "mask" in obj:
                obj["mask"] = (
                    image_utils.urle_to_rle(obj["mask"])
                    if obj["mask"]
                    and "counts" in obj["mask"]
                    and "size" in obj["mask"]
                    and len(obj["mask"]["size"]) == 2
                    else {"size": [0, 0], "counts": b""}
                )
            if "keypoints" in obj:
                obj["keypoints"] = (
                    {
                        "template_id": obj["keypoints"]["template_id"],
                        "coords": [
                            coord
                            for pt in obj["keypoints"]["vertices"]
                            for coord in (pt["x"], pt["y"])
                        ],
                        "states": [
                            (
                                pt["features"]["state"]
                                if "features" in pt and "state" in pt["features"]
                                else "visible"
                            )
                            for pt in obj["keypoints"]["vertices"]
                        ],
                    }
                    if obj["keypoints"] and "vertices" in obj["keypoints"]
                    else {
                        "template_id": "None",
                        "coords": [0, 0],
                        "states": ["invisible"],
                    }
                )
            if "features" in obj:
                for feat in obj["features"].values():
                    # TODO coerce to type feat["dtype"] (need mapping dtype string to type)
                    obj[feat["name"]] = feat["value"]

        return pa.Table.from_pylist(
            objs,
            schema=table.schema,
        )

    def convert_item_to_pyarrow(table, item):
        # Convert item to PyArrow
        pyarrow_item = {}

        # ID
        pyarrow_item["id"] = item.id
        pyarrow_item["split"] = item.split

        # Features
        if item.features is not None:
            for feat in item.features.values():
                # TODO coerce to type feat["dtype"] (need mapping dtype string to type)
                pyarrow_item[feat["name"]] = feat["value"]

        return pa.Table.from_pylist(
            [pyarrow_item],
            schema=table.schema,
        )

    # items features
    item_table = dataset.open_table("item")
    item_table.delete(f"id in ('{item.id}')")
    item_table.add(convert_item_to_pyarrow(item_table, item))

    # TODO : how to select the correct OBJECT table name ? store it in front ?
    obj_table = dataset.open_table("objects")
    obj_table.delete(f"item_id in ('{item.id}')")

    # items objects (and tracklets for video)
    if item.objects:
        if item.type == "image":
            obj_table.add(convert_objects_to_pyarrow(obj_table, item.objects))
        elif item.type == "video":
            obj_add = []
            tracklet_add = []

            # TODO : how to select the correct TRACKLET table name ? store it in front ?
            tracklet_table = dataset.open_table("tracklets")
            tracklet_table.delete(f"item_id in ('{item.id}')")

            for track in item.objects:
                for tracklet in track["track"]:
                    tracklet_id = (
                        tracklet["id"] if "id" in tracklet else shortuuid.uuid()
                    )
                    tracklet_add.append(
                        {
                            "id": tracklet_id,
                            "item_id": item.id,
                            "track_id": track["id"],
                            "start_timestep": tracklet[
                                "start"
                            ],  # TODO timestamp/timestep, front keep only one... ?
                            "start_timestamp": tracklet["start"],
                            "end_timestep": tracklet["end"],
                            "end_timestamp": tracklet["end"],
                        }
                    )
                if "boxes" in track:
                    for box in track["boxes"]:
                        obj_add.append(
                            {
                                "id": box["id"] if "id" in box else shortuuid.uuid(),
                                "item_id": item.id,
                                "view_id": track["view_id"],
                                "tracklet_id": box["tracklet_id"],
                                "frame_idx": box["frame_index"],
                                "is_key": box["is_key"],
                                "is_thumbnail": (
                                    box["is_thumbnail"]
                                    if "is_thumbnail" in box
                                    else False
                                ),
                                "bbox": {
                                    "coords": box["coords"],
                                    "format": box["format"],
                                    "is_normalized": box["is_normalized"],
                                    "confidence": box["confidence"],
                                },
                            }
                        )
                if "keypoints" in track:
                    for keypoints in track["keypoints"]:
                        obj_add.append(
                            {
                                "id": (
                                    keypoints["id"]
                                    if "id" in keypoints
                                    else shortuuid.uuid()
                                ),
                                "item_id": item.id,
                                "view_id": track["view_id"],
                                "tracklet_id": keypoints["tracklet_id"],
                                "frame_idx": keypoints["frame_index"],
                                "is_key": keypoints["is_key"],
                                "is_thumbnail": (
                                    keypoints["is_thumbnail"]
                                    if "is_thumbnail" in keypoints
                                    else False
                                ),
                                "keypoints": keypoints,
                            }
                        )

            if tracklet_add:
                tracklet_table.add(
                    convert_objects_to_pyarrow(tracklet_table, tracklet_add)
                )
            if obj_add:
                obj_table.add(convert_objects_to_pyarrow(obj_table, obj_add))

            # tracklet_table.to_lance().cleanup_old_versions()

    # Clear change history to prevent dataset from becoming too large
    # obj_table.to_lance().cleanup_old_versions()
    # TODO: ther is a lancedb utility to "reshape" table after updates, to keep it "clean"
    # Maybe we should use it ?

    # Return response
    return Response()


@router.get(
    "/items/{item_id}/embeddings/{model_id}",
    response_model=DatasetItem,
)
async def get_item_embeddings(  # noqa: D417
    ds_id: str,
    item_id: str,
    model_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetItem:  # type: ignore
    """Load dataset item embeddings.

    Args:
        ds_id (str): Dataset ID
        item_id (str): Item ID
        model_id (str): Model ID (ONNX file path)
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        item = dataset.read_embedding(item_id)

        # Return dataset item embeddings
        if item:
            return item
        raise HTTPException(
            status_code=404,
            detail=(
                f"No embeddings found for item '{item_id}' "
                f"with model '{model_id}' in dataset",
            ),
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )
