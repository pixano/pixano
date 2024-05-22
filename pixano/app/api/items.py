# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params

from pixano.app.settings import Settings, get_settings
from pixano.datasets import Dataset, DatasetItem
import pixano.datasets.dataset_explorer as de
from pixano.datasets.features import Image, SequenceFrame
from pixano.datasets.features.schemas.group import _SchemaGroup


# TMP legacy
from typing import Optional
from pydantic import BaseModel
from collections import defaultdict


class FrontDatasetItem(BaseModel):
    """Front format DatasetItem"""

    id: str
    datasetId: str
    type: str
    # original_id: Optional[str] = None
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
    """## Get all dataset items ids

    Args:
        ds_id (str): dataset id

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
                    view_type = "image"  # TMP (previews video pas encore générés, alors on met une image pour l'instant)  "video"  # or "sequenceframe" ?
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

    if dataset:
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
            if isinstance(view_item, Image):
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
            elif (
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

        # objects
        # TMP NOTE : the objects contents may still be subject to change -- WIP
        objects = []
        for obj_group in groups[_SchemaGroup.OBJECT]:
            if view_type == "image":
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
                                ]
                            },  # ????
                            # bbox/mask/whatelse?
                            "bbox": obj.bbox if hasattr(obj, "bbox") else None,
                            "mask": obj.mask if hasattr(obj, "mask") else None,
                        }
                        for obj in getattr(item, obj_group)
                    ]
                )
            else:  # video
                # Create a dict to organize objects in tracks/tracklet per view
                tracks_dict = defaultdict(
                    lambda: defaultdict(lambda: defaultdict(list))
                )
                for obj in getattr(item, obj_group):
                    tracks_dict[obj.view_id][obj.track_id][obj.tracklet_id].append(obj)

                # Sort tracklets by frame_idx
                for view_id, tracks in tracks_dict.items():
                    for track_id, tracklets in tracks.items():
                        for tracklet_id, tracklet_objs in tracklets.items():
                            tracklet_objs.sort(key=lambda x: x.frame_idx)

                all_tracks = []
                for view_id, tracks in tracks_dict.items():
                    view_tracks = []
                    for track_id, tracklets in tracks.items():
                        track = {"track_id": track_id, "tracklets": []}
                        for tracklet_id, tracklet_objs in tracklets.items():
                            tracklet = {
                                "tracklet_id": tracklet_id,
                                "tracklet_objs": [
                                    {
                                        "keyBoxes": {
                                            **vars(obj.bbox),
                                            "frame_index": obj.frame_idx,
                                            "is_keypoint": i % (len(tracklet_objs) - 1)
                                            == 0,
                                        },
                                        "obj_features": obj,  # we put the whole obj to get features from it below
                                    }
                                    for i, obj in enumerate(tracklet_objs)
                                ],
                            }
                            track["tracklets"].append(tracklet)
                        view_tracks.append(track)
                    all_tracks.append({"view_id": view_id, "tracks": view_tracks})

                for view_tracks in all_tracks:
                    for track in view_tracks["tracks"]:
                        # --NOTE we assume features are per track.
                        # --It's not totally realistic, should need future brainstorm
                        # we take features from the first object of first tracklet
                        feature_obj_ref = track["tracklets"][0]["tracklet_objs"][0][
                            "obj_features"
                        ]
                        objects.append(
                            {
                                "id": track["track_id"],
                                "datasetItemType": view_type,
                                "item_id": item_id,
                                "source_id": "Ground Truth",  # ?? must ensure source
                                "view_id": view_tracks["view_id"],
                                "features": {
                                    fname: {
                                        "name": fname,
                                        "dtype": type(
                                            getattr(feature_obj_ref, fname)
                                        ).__name__,
                                        "value": getattr(feature_obj_ref, fname),
                                    }
                                    for fname in vars(feature_obj_ref).keys()
                                    if fname
                                    not in [
                                        "id",
                                        "item_id",
                                        "source_id",
                                        "view_id",
                                        "bbox",
                                        "mask",
                                        # "track_id",  #TMP let this one to have at least a feature
                                        "tracklet_id",
                                        "timestamp",
                                        "frame_idx",
                                    ]  # TODO: define list of unwanted features
                                },
                                "track": [
                                    {
                                        "id": tracklet["tracklet_id"],
                                        "start": tracklet["tracklet_objs"][0][
                                            "keyBoxes"
                                        ]["frame_index"],
                                        "end": tracklet["tracklet_objs"][-1][
                                            "keyBoxes"
                                        ]["frame_index"],
                                        "keyBoxes": [
                                            obj["keyBoxes"]
                                            for obj in tracklet["tracklet_objs"]
                                        ],
                                    }
                                    for tracklet in track["tracklets"]
                                ],
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

        # Return dataset item
        if front_item:
            return front_item
        raise HTTPException(
            status_code=404,
            detail=f"Item '{item_id}' not found in dataset",
        )
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


@router.post("/items/{item_id}", response_model=DatasetItem)
async def post_dataset_item(  # noqa: D417
    ds_id: str,
    item: DatasetItem,  # type: ignore
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Save dataset item.

    Args:
        ds_id (str): Dataset ID
        item (DatasetItem): Item to save
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    if dataset:
        # Save dataset item
        dataset.save_item(item)

        # Return response
        return Response()
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )


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
