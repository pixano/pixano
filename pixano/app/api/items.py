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
    Annotation,
    BaseSchema,
    BBox,
    CompressedRLE,
    Entity,
    Image,
    KeyPoints,
    SequenceFrame,
    _SchemaGroup,
    is_bbox,
    is_compressed_rle,
    is_keypoints,
    is_track,
    is_tracklet,
)
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
        items = dataset.get_dataset_items(
            ids
        )  # future API: will get only relevant info (ex:  we don't need objects, all frames, etc..)
        if items:
            # convert CustomDatasetItem (from new API) to TableData
            # build ColDesc
            groups = defaultdict(list)
            for tname in vars(items[0]).keys():
                found_group = _SchemaGroup.ITEM  # if no matching group (-> it's not a table name), it is in ITEM
                for group, tnames in dataset.schema._groups.items():
                    if tname in tnames:
                        found_group = group
                        break
                groups[found_group].append(tname)
            cols = []
            for feat in groups[_SchemaGroup.VIEW]:
                view_item = getattr(items[0], feat)
                if isinstance(view_item, Image):
                    view_type = "image"
                elif isinstance(view_item, list) and len(view_item) > 0 and isinstance(view_item[0], SequenceFrame):
                    # TMP (video previews are not generated yet
                    # so we put an image for now ("video"  # or "sequenceframe" ?)
                    view_type = "image"
                else:
                    print("ERROR: unknown view type", type(view_item), view_item)
                    view_type = type(view_item).__name__
                cols.append(de.ColDesc(name=feat, type=view_type))
            for feat in groups[_SchemaGroup.ITEM]:
                cols.append(de.ColDesc(name=feat, type=type(getattr(items[0], feat)).__name__))

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
                        isinstance(view_item, list) and len(view_item) > 0 and isinstance(view_item[0], SequenceFrame)
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
                pagination=de.PaginationInfo(current=start, size=raw_params.limit, total=total),
                sem_search=[],
            )
        raise HTTPException(
            status_code=404,
            detail=(f"No items found with page parameters (start {start}, " f"stop {stop}) in dataset",),
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
        items = dataset.search_items(raw_params.limit, raw_params.offset, query)  # type: ignore[attr-defined]

        # Return dataset items
        if items:
            return create_page(items, total=total, params=params)
        raise HTTPException(status_code=404, detail=f"No items found for query '{query}' in dataset")
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


def getFeatures(obj: BaseSchema, ignore_cls, add_fields: list[str] = []) -> dict[str, dict]:
    """Create features of obj, without considering fields from ignore_cls.

    Args:
        obj (BaseSchema): obj whose features are extracted from
        ignore_cls (_type_): parent class of obj whose fields are excluded from features
        add_fields (list[str]): fields to add (removed from ignored fields of ignore_cls)

    Returns:
        dict[str, dict]: _description_
    """
    ignore_fields = []
    for base in ignore_cls.__mro__:
        if "__annotations__" in base.__dict__:
            ignore_fields.extend([field for field in base.__annotations__ if field not in add_fields])
    return {
        feat_name: {
            "name": feat_name,
            "dtype": type(getattr(obj, feat_name)).__name__,
            "value": getattr(obj, feat_name),
        }
        for feat_name in vars(obj).keys()
        if feat_name not in ignore_fields and type(getattr(obj, feat_name)).__name__ in ["int", "float", "str", "bool"]
    }


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

    groups = dataset.schema._groups

    # Load dataset item
    item = dataset.get_dataset_items([item_id])[0]

    # Item Features
    not_item_meta = ["id", "split"]
    for group, k in groups.items():
        if group != _SchemaGroup.ITEM:
            not_item_meta.extend(k)
    item_features = {
        feat: {
            "name": feat,
            "dtype": type(getattr(item, feat)).__name__,
            "value": getattr(item, feat),
        }
        for feat in vars(item).keys()
        if feat not in not_item_meta
    }

    # Views
    views = {}
    view_type = "image"
    for view_name in groups[_SchemaGroup.VIEW]:
        view_item = getattr(item, view_name)
        if isinstance(view_item, list) and len(view_item) > 0 and isinstance(view_item[0], SequenceFrame):
            views[view_name] = sorted(
                [
                    {
                        "id": frame.id,
                        "type": "image",  # note: it's an image frame from a video
                        "frame_index": frame.frame_index,
                        "uri": "data/" + dataset.path.name + "/media/" + frame.url,
                        # "uri": view_item[0].open(dataset.path / "media"),  # TMP!! need to give vid..?
                        "thumbnail": None,  # frame.open(dataset.path / "media"),
                        "features": getFeatures(frame, SequenceFrame, ["width", "height"]),
                    }
                    for frame in view_item
                ],
                key=lambda x: x["frame_index"],
            )
            view_type = "video"
        elif isinstance(view_item, Image):
            views[view_name] = {  # type: ignore[assignment]
                "id": view_item.id,
                "type": "image",
                "uri": "data/" + dataset.path.name + "/media/" + view_item.url,
                "thumbnail": None,  # view_item.open(dataset.path / "media"),
                "features": getFeatures(view_item, Image, ["width", "height"]),
            }

    # Objects
    # TMP NOTE : the objects contents may still be subject to change -- WIP
    objects = []
    NoneBBox = BBox.none()
    NoneMask = CompressedRLE.none()
    NoneKeypoints = KeyPoints.none()

    # Note: This is used to find the entity of an annotation
    # (see "Entity features" part below)
    # this could be replaced by new python API get_data(...?)
    # But, it is used for retrieving features at various levels
    # and gather them at annotation level...
    # May need to rework / think more about this
    def findEntity(ann: Annotation) -> Entity | None:
        for group_entity in groups[_SchemaGroup.ENTITY]:
            entity = next(
                (entity for entity in getattr(item, group_entity) if entity.id == ann.entity_ref.id),
                None,
            )
            if entity:
                return entity
        return None

    if view_type == "image":
        for annotation_group in groups[_SchemaGroup.ANNOTATION]:
            for annotation in getattr(item, annotation_group):
                # Entity features
                features = {}
                ann_entity = findEntity(annotation)
                if ann_entity is not None:
                    features.update(getFeatures(ann_entity, Entity))

                obj = {
                    "id": annotation.id,
                    "datasetItemType": view_type,
                    "item_id": item_id,
                    "source_id": "Ground Truth",  # ??
                }
                if is_bbox(type(annotation), False) and annotation != NoneBBox:
                    features.update(getFeatures(annotation, BBox))
                    obj["bbox"] = {
                        "coords": annotation.xywh_coords,
                        "format": "xywh",
                        "is_normalised": annotation.is_normalized,
                        "confidence": annotation.confidence,
                        "view_id": annotation.view_ref.name,  # danger faux-ami !
                    }
                if is_compressed_rle(type(annotation), False) and annotation != NoneMask:
                    features.update(getFeatures(annotation, CompressedRLE))
                    urle = image_utils.rle_to_urle(
                        {
                            "size": annotation.size,
                            "counts": annotation.counts,
                        }
                    )
                    obj["mask"] = {
                        **vars(urle),
                        "view_id": annotation.view_ref.name,
                    }
                if is_keypoints(type(annotation), False) and annotation != NoneKeypoints:
                    features.update(getFeatures(annotation, KeyPoints))
                    obj["keypoints"] = {
                        "template_id": annotation.template_id,
                        "vertices": annotation.map_back2front_vertices(),
                        "view_id": annotation.view_ref.name,
                    }
                obj["features"] = features
                objects.append(obj)
    else:  # video
        tracks = defaultdict(list)
        entity_id = defaultdict(list)

        # gather tracklets by track
        for annotation_group in groups[_SchemaGroup.ANNOTATION]:
            for annotation in getattr(item, annotation_group):
                if is_tracklet(type(annotation)):
                    tracks[annotation.entity_ref.id].append(annotation)

        # match track_id with spatial object id if exist
        for entity_group in groups[_SchemaGroup.ENTITY]:
            for entity in getattr(item, entity_group):
                if is_track(type(entity)) and entity.id not in entity_id:
                    entity_id[entity.id].append(entity.id)
                elif entity.parent_ref.id != "":
                    entity_id[entity.parent_ref.id].append(entity.id)

        for track_id, tracklets in tracks.items():
            # if track_id.startswith("track_1") or track_id.startswith("track_2") or track_id.startswith("track_3"):
            #     continue
            bboxes = []
            keypoints = []
            features = {}
            # Note: for now, annotation features keeps overwriting for each annotation...
            # We need to be able to manage lower level features in front. (will be done in front data refactor)
            for annotation_group in groups[_SchemaGroup.ANNOTATION]:
                for annotation in getattr(item, annotation_group):
                    # if annotation.view_ref.id == "":
                    #     # ignore if annotation is not linked to a view
                    #     # Note: Maybe we should still gather features ?
                    #     continue
                    if is_tracklet(type(annotation)):
                        continue
                    if annotation.entity_ref.id in entity_id[track_id]:
                        # get frame_index from annotation.view_ref
                        frame_index = next(
                            (
                                view["frame_index"]
                                for view in views[annotation.view_ref.name]
                                if view["id"] == annotation.view_ref.id
                            ),
                            -1,
                        )
                        if frame_index == -1:
                            print(
                                "Warning: Annotation found that doesn't match to any frame",
                                annotation,
                            )
                            continue

                        # Entity features
                        ann_entity = findEntity(annotation)
                        if ann_entity:
                            features.update(getFeatures(ann_entity, Entity))

                        if is_bbox(type(annotation), False) and annotation != NoneBBox:
                            features.update(getFeatures(annotation, BBox))
                            bboxes.append(
                                {
                                    "coords": annotation.xywh_coords,
                                    "format": "xywh",
                                    "is_normalised": annotation.is_normalized,
                                    "confidence": annotation.confidence,
                                    "view_id": annotation.view_ref.name,  # danger faux-ami !
                                    "frame_index": frame_index,
                                    "is_key": (annotation.is_key if hasattr(annotation, "is_key") else True),
                                    "is_thumbnail": False,
                                    "tracklet_id": annotation.entity_ref.id,
                                }
                            )
                        if is_keypoints(type(annotation), False) and annotation != NoneKeypoints:
                            features.update(getFeatures(annotation, KeyPoints))
                            keypoints.append(
                                {
                                    "template_id": annotation.template_id,
                                    "vertices": annotation.map_back2front_vertices(),
                                    "frame_index": frame_index,
                                    "view_id": annotation.view_ref.name,
                                    "is_key": (annotation.is_key if hasattr(annotation, "is_key") else True),
                                    "tracklet_id": annotation.entity_ref.id,
                                }
                            )

            # sort annotations by frame_index
            bboxes.sort(key=lambda bbox: bbox["frame_index"])
            keypoints.sort(key=lambda kpt: kpt["frame_index"])

            # set thumbnail to first bbox
            if len(bboxes) > 0:
                bboxes[0]["is_thumbnail"] = True

            objects.append(
                {
                    "id": track_id,
                    "datasetItemType": view_type,
                    "item_id": item_id,
                    "source_id": "Ground Truth",  # ?? must ensure source
                    "features": features,
                    "track": [
                        {
                            "id": tracklet.id,
                            "start": (
                                tracklet.start_timestep
                                if hasattr(tracklet, "start_timestep")
                                else tracklet.start_timestamp
                            ),
                            "end": (
                                tracklet.end_timestep if hasattr(tracklet, "end_timestep") else tracklet.end_timestamp
                            ),
                            "view_id": tracklet.view_ref.name,
                        }
                        for tracklet in tracklets
                    ],
                    "boxes": bboxes,
                    "keypoints": keypoints,
                }
            )
            # print("OBJ", objects[-1])

    front_item = FrontDatasetItem(
        id=item.id,
        type=view_type,
        datasetId=ds_id,
        split=item.split,
        views=views,
        objects=objects,
        features=item_features,
        embeddings={},  # TODO
    )

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
                        "coords": [coord for pt in obj["keypoints"]["vertices"] for coord in (pt["x"], pt["y"])],
                        "states": [
                            (pt["features"]["state"] if "features" in pt and "state" in pt["features"] else "visible")
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
                    tracklet_id = tracklet["id"] if "id" in tracklet else shortuuid.uuid()
                    tracklet_add.append(
                        {
                            "id": tracklet_id,
                            "item_id": item.id,
                            "track_id": track["id"],
                            "start_timestep": tracklet["start"],  # TODO timestamp/timestep, front keep only one... ?
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
                                "is_thumbnail": (box["is_thumbnail"] if "is_thumbnail" in box else False),
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
                                "id": (keypoints["id"] if "id" in keypoints else shortuuid.uuid()),
                                "item_id": item.id,
                                "view_id": track["view_id"],
                                "tracklet_id": keypoints["tracklet_id"],
                                "frame_idx": keypoints["frame_index"],
                                "is_key": keypoints["is_key"],
                                "is_thumbnail": (keypoints["is_thumbnail"] if "is_thumbnail" in keypoints else False),
                                "keypoints": keypoints,
                            }
                        )

            if tracklet_add:
                tracklet_table.add(convert_objects_to_pyarrow(tracklet_table, tracklet_add))
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
        try:
            embeddings = dataset.get_data(_SchemaGroup.EMBEDDING, [item_id])[0]  # type: ignore[arg-type]
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=("No embeddings table in dataset"),
            )

        # Return dataset item embeddings
        if embeddings:
            return embeddings
        raise HTTPException(
            status_code=404,
            detail=(f"No embeddings found for item '{item_id}' " f"with model '{model_id}' in dataset",),
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )
