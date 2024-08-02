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
from pixano.datasets.dataset_schema import SchemaRelation
from pixano.datasets.features import (
    Annotation,
    BaseSchema,
    BBox,
    CompressedRLE,
    Entity,
    EntityRef,
    Image,
    ItemRef,
    KeyPoints,
    SequenceFrame,
    Tracklet,
    ViewRef,
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


class SaveDatasetItem(BaseModel):
    """Front format SaveDatasetItem."""

    id: str
    split: str
    item_features: Optional[dict] = None
    save_data: list = []


router = APIRouter(tags=["items"], prefix="/datasets/{ds_id}")


@router.get("/item_ids", response_model=list[str])
async def get_dataset_item_ids(
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[str]:
    """## Get all dataset items ids.

    Args:
        ds_id: dataset id
        settings: settings

    Returns:
        All items ids.
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
        ds_id: Dataset ID.
        settings: App settings.
        params: Pagination parameters (offset and limit).

    Returns:
        Dataset explorer page.
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
                sem_search=["TOTO"],
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
        ds_id: Dataset ID.
        query: Search query.
        params: Pagination parameters (offset and limit).

    Returns:
        Dataset items page.
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


def get_features(obj: BaseSchema, ignore_cls: type, add_fields: list[str] = []) -> dict[str, dict]:
    """Create features of obj, without considering fields from ignore_cls.

    Args:
        obj: obj whose features are extracted from.
        ignore_cls: parent class of obj whose fields are excluded from features.
        add_fields: fields to add (removed from ignored fields of ignore_cls).

    Returns:
        The features of obj.
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
        ds_id: Dataset ID
        item_id: Item ID

    Returns:
        The front dataset item.
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
                        "features": get_features(frame, SequenceFrame, ["width", "height"]),
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
                "features": get_features(view_item, Image, ["width", "height"]),
            }

    # Objects
    # TMP NOTE : the objects contents may still be subject to change -- WIP
    objects = []
    none_bbox = BBox.none()
    none_mask = CompressedRLE.none()
    none_keypoints = KeyPoints.none()

    def find_top_entity(ann: Annotation) -> Entity | None:
        """Find top entity of an annotation.

        Args:
            ann: annotation.

        Returns:
            top Entity for this annotation.
        """
        try:
            return find_top_parent_entity(ann.entity)
        except ValueError:
            return None

    def find_top_parent_entity(entity: Entity) -> Entity | None:
        """Find top parent entity of an entity.

        Args:
            entity: The entity.

        Returns:
            top parent Entity for this entity.
        """
        try:
            return find_top_parent_entity(entity.parent)
        except ValueError:
            return entity

    if view_type == "image":
        for annotation_group in groups[_SchemaGroup.ANNOTATION]:
            for annotation in getattr(item, annotation_group):
                # Entity features
                features = {}
                ann_entity = find_top_entity(annotation)
                if ann_entity is not None:  # Note: should never be None
                    features.update(get_features(ann_entity, Entity))

                obj = {
                    "id": ann_entity.id if ann_entity else annotation.id,
                    "datasetItemType": view_type,
                    "item_id": item_id,
                    "source_id": "Ground Truth",  # ??
                }
                if is_bbox(type(annotation), False) and annotation != none_bbox:
                    features.update(get_features(annotation, BBox))
                    obj["bbox"] = {
                        "id": annotation.id,
                        "ref_name": annotation_group,
                        "entity_ref": {"id": annotation.entity_ref.id, "name": annotation.entity_ref.name},
                        "coords": annotation.xywh_coords,
                        "format": "xywh",
                        "is_normalized": annotation.is_normalized,
                        "confidence": annotation.confidence,
                        "view_id": annotation.view_ref.name,  # danger faux-ami !
                    }
                if is_compressed_rle(type(annotation), False) and annotation != none_mask:
                    features.update(get_features(annotation, CompressedRLE))
                    urle = image_utils.rle_to_urle(
                        {
                            "size": annotation.size,
                            "counts": annotation.counts,
                        }
                    )
                    obj["mask"] = {
                        **vars(urle),
                        "id": annotation.id,
                        "ref_name": annotation_group,
                        "entity_ref": {"id": annotation.entity_ref.id, "name": annotation.entity_ref.name},
                        "view_id": annotation.view_ref.name,
                    }
                if is_keypoints(type(annotation), False) and annotation != none_keypoints:
                    features.update(get_features(annotation, KeyPoints))
                    obj["keypoints"] = {
                        "id": annotation.id,
                        "ref_name": annotation_group,
                        "entity_ref": {"id": annotation.entity_ref.id, "name": annotation.entity_ref.name},
                        "template_id": annotation.template_id,
                        "vertices": annotation.map_back2front_vertices(),
                        "view_id": annotation.view_ref.name,
                    }
                obj["features"] = features
                objects.append(obj)
    else:  # video
        trackid_to_tracklets_list = defaultdict(list)  # trackid2trackletslist
        trackid_to_entityid_list = defaultdict(list)  # trackid2entityidlist
        entity_id2trackid = {}
        trackid2track = {}

        ## Store a cache of references for faster loading
        # gather tracklets for each track
        for annotation_group in groups[_SchemaGroup.ANNOTATION]:
            for annotation in getattr(item, annotation_group):
                if is_tracklet(type(annotation)):
                    trackid_to_tracklets_list[annotation.entity_ref.id].append(annotation)

        # gather entities/track references
        for entity_group in groups[_SchemaGroup.ENTITY]:
            for entity in getattr(item, entity_group):
                if is_track(type(entity)):
                    trackid2track[entity.id] = entity
                if is_track(type(entity)) and entity.id not in trackid_to_entityid_list:
                    trackid_to_entityid_list[entity.id].append(entity.id)
                    entity_id2trackid[entity.id] = entity.id
                elif entity.parent_ref.id != "":
                    trackid_to_entityid_list[entity.parent_ref.id].append(entity.id)
                    entity_id2trackid[entity.id] = entity.parent_ref.id

        # gather annotations/track references
        for annotation_group in groups[_SchemaGroup.ANNOTATION]:
            for annotation in getattr(item, annotation_group):
                if is_tracklet(type(annotation)):
                    continue
                entity_id = annotation.entity_ref.id
                track_id = entity_id2trackid[entity_id]

        # Load all tracks related data
        track_bboxes = defaultdict(list)
        track_keypoints = defaultdict(list)
        track_features: dict[str, dict] = defaultdict(dict)
        kept_track_ids = []
        for annotation_group in groups[_SchemaGroup.ANNOTATION]:
            for annotation in getattr(item, annotation_group):
                if is_tracklet(type(annotation)):
                    continue
                entity_id = annotation.entity_ref.id
                track_id = entity_id2trackid[entity_id]
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

                # find tracklet_id for current annotation
                # NOTE: not really sure it's usefull... will disappear after front refactor
                # based on:
                # - annotation.entity_ref.id
                # - annotation.view_ref
                # - frame_index
                tracklet_id = next(
                    (
                        tracklet.id
                        for tracklet in trackid_to_tracklets_list[entity_id2trackid[annotation.entity_ref.id]]
                        if (
                            tracklet.view_ref.name == annotation.view_ref.name
                            and tracklet.start_timestep <= frame_index
                            and frame_index <= tracklet.end_timestep
                        )
                    ),
                    None,
                )
                if tracklet_id is None:
                    # if annotation has no associated tracklet, bind it to its entity (should not happens)
                    print(
                        "Warning: Annotation found without a tracklet",
                        annotation,
                    )
                    tracklet_id = (annotation.entity_ref.id,)

                kept_track_ids.append(track_id)

                # ann_entity = find_top_entity(annotation) # Slow general approach
                ann_entity = trackid2track[track_id]  # Fast specific approach

                if ann_entity:
                    track_features[track_id].update(get_features(ann_entity, Entity))

                if is_bbox(type(annotation), False) and annotation != none_bbox:
                    track_bboxes[track_id].append(
                        {
                            "id": annotation.id,
                            "ref_name": annotation_group,
                            "entity_ref": {"id": annotation.entity_ref.id, "name": annotation.entity_ref.name},
                            "coords": annotation.xywh_coords,
                            "format": "xywh",
                            "is_normalized": annotation.is_normalized,
                            "confidence": annotation.confidence,
                            "view_id": annotation.view_ref.name,
                            "frame_index": frame_index,
                            "is_key": (annotation.is_key if hasattr(annotation, "is_key") else True),
                            "is_thumbnail": False,
                            "tracklet_id": tracklet_id,
                        }
                    )

                if is_keypoints(type(annotation), False) and annotation != none_keypoints:
                    track_keypoints[track_id].append(
                        {
                            "id": annotation.id,
                            "ref_name": annotation_group,
                            "entity_ref": {"id": annotation.entity_ref.id, "name": annotation.entity_ref.name},
                            "template_id": annotation.template_id,
                            "vertices": annotation.map_back2front_vertices(),
                            "frame_index": frame_index,
                            "view_id": annotation.view_ref.name,
                            "is_key": (annotation.is_key if hasattr(annotation, "is_key") else True),
                            "tracklet_id": tracklet_id,
                        }
                    )

        objects = []
        for track_id in sorted(set(kept_track_ids)):
            bboxes = track_bboxes[track_id]
            keypoints = track_keypoints[track_id]
            features = track_features[track_id]
            # sort annotations by frame_index
            bboxes.sort(key=lambda bbox: bbox["frame_index"])
            keypoints.sort(key=lambda kpt: kpt["frame_index"])
            # get tracklets
            tracklets = trackid_to_tracklets_list[track_id]
            tracklets.sort(key=lambda x: (x.view_ref.name, x.start_timestamp))
            # set thumbnail to first bbox
            if len(bboxes) > 0:
                bboxes[0]["is_thumbnail"] = True
            objects.append(
                {
                    "id": track_id,
                    "ref_name": "top_entity",
                    "datasetItemType": view_type,
                    "item_id": item_id,
                    "source_id": "Ground Truth",
                    "features": features,
                    "track": [
                        {
                            "id": tracklet.id,
                            "ref_name": "tracklet",
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


@router.post("/items/{item_id}", response_model=SaveDatasetItem)
async def post_dataset_item(  # noqa: D417
    ds_id: str,
    item: SaveDatasetItem,  # type: ignore
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Save dataset item.

    Args:
        ds_id: Dataset ID
        item: Item to save
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
        )

    def convert_item_to_pyarrow(table, item):
        # Convert item to PyArrow
        pyarrow_item = {}

        # ID
        pyarrow_item["id"] = item.id
        pyarrow_item["split"] = item.split

        # Features
        if item.item_features is not None:
            for feat in item.item_features.values():
                # TODO coerce to type feat["dtype"] (need mapping dtype string to type)
                pyarrow_item[feat["name"]] = feat["value"]

        return pa.Table.from_pylist(
            [pyarrow_item],
            schema=table.schema,
        )

    def find_table(ref_name: str) -> tuple[str, type | None]:
        tclass = None
        if not ref_name or ref_name == "":
            return "", None
        if ref_name == "item":
            return "item", None
        if ref_name == "bbox":
            tclass = BBox
        if ref_name == "mask":
            tclass = CompressedRLE
        if ref_name == "keypoints":
            tclass = KeyPoints
        if ref_name == "tracklet":
            tclass = Tracklet
        if ref_name == "top_entity":
            tclass = Entity
        if tclass is not None:
            table_name = next((k for k, v in dataset.schema.schemas.items() if issubclass(v, tclass)), None)
            if table_name:
                return table_name, tclass
            # create a table for tclass
            # a table with name ref_name may already exist (but not in dataset schema)
            # so we drop table before
            dataset._db_connection.drop_table(ref_name, ignore_missing=True)
            dataset.create_table(ref_name, tclass, SchemaRelation.MANY_TO_ONE)
            return ref_name, tclass
        return "", None

    # items features
    item_table = dataset.open_table("item")
    item_table.delete(f"id in ('{item.id}')")
    item_table.add(convert_item_to_pyarrow(item_table, item))

    table_data = defaultdict(list)
    track_entity_tname, _ = find_table("top_entity")

    for i, save_it in enumerate(item.save_data):
        if save_it["change_type"] == "add_or_update":
            table_name, tclass = find_table(save_it["data"]["ref_name"])
            if table_name == "":
                continue
            obj = save_it["data"]
            if "id" not in obj:
                obj["id"] = shortuuid.uuid()
            obj["item_ref"] = ItemRef(id=item.id, name="item")
            # some annotations (eg. tracklets) doesn't have a view_ref, or at least no frame_index
            obj["view_ref"] = ViewRef.none()
            if "view_id" in obj:
                if save_it["is_video"]:
                    if save_it["is_video"] and "frame_index" in obj:
                        images = dataset.get_data(table_name=str(obj["view_id"]), item_ids=[item.id])
                        view_ref_id = next(im for im in images if im.frame_index == obj["frame_index"]).id
                        obj["view_ref"] = ViewRef(id=view_ref_id, name=obj["view_id"])
                    else:
                        obj["view_ref"] = ViewRef(id="", name=obj["view_id"])
                else:
                    images = dataset.get_data(table_name=str(obj["view_id"]), item_ids=[item.id])
                    if len(images) == 1:
                        obj["view_ref"] = ViewRef(id=images[0].id, name=obj["view_id"])
                    else:
                        obj["view_ref"] = ViewRef(id="", name=obj["view_id"])
            obj["entity_ref"] = EntityRef(id=obj["entity_ref"]["id"], name=track_entity_tname)
            if "features" in obj:
                for feat in obj["features"].values():
                    # TODO coerce to type feat["dtype"] (need mapping dtype string to type)
                    obj[feat["name"]] = feat["value"]

            if tclass == BBox:
                pass
            if tclass == CompressedRLE:
                mask = image_utils.urle_to_rle({"counts": obj["counts"], "size": obj["size"]})
                obj["counts"] = mask["counts"]
                obj["size"] = mask["size"]
            if tclass == KeyPoints:
                obj["coords"] = [coord for pt in obj["vertices"] for coord in (pt["x"], pt["y"])]
                obj["states"] = [
                    (pt["features"]["state"] if "features" in pt and "state" in pt["features"] else "visible")
                    for pt in obj["vertices"]
                ]
            if tclass == Entity:
                obj["parent_ref"] = EntityRef.none()
            if tclass == Tracklet:
                obj["start_timestep"] = obj["start"]
                obj["end_timestep"] = obj["end"]
                # TODO correct timestamps !
                obj["start_timestamp"] = -1
                obj["end_timestamp"] = -1

            table_data[table_name].append(dataset.schema.schemas[table_name](**obj))
        if save_it["change_type"] == "delete":
            for ref, ids in save_it["data"].items():
                if ref != "" and len(ids) > 0:
                    table_name, _ = find_table(ref)
                    if table_name != "":
                        dataset.delete_data(table_name, ids)

    for tname, tdata in table_data.items():
        dataset.update_data(tname, tdata)

    # Clear change history to prevent dataset from becoming too large
    # tables.to_lance().cleanup_old_versions()
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
        ds_id: Dataset ID
        item_id: Item ID
        model_id: Model ID (ONNX file path)
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        try:
            embeddings = dataset.get_data(_SchemaGroup.EMBEDDING.value, [item_id])[0]  # type: ignore[arg-type]
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
