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


class LegacyDatasetItem(BaseModel):
    id: str
    type: str
    original_id: Optional[str] = None
    split: str
    features: Optional[dict] = None
    views: Optional[dict] = None
    objects: Optional[list] = None
    embeddings: Optional[dict] = None


router = APIRouter(tags=["items"], prefix="/datasets/{ds_id}")


# @router.get("/items", response_model=Page[LegacyDatasetItem])
# async def get_dataset_items(  # noqa: D417
#     ds_id: str,
#     settings: Annotated[Settings, Depends(get_settings)],
#     params: Params = Depends(),
# ) -> Page[LegacyDatasetItem]:  # type: ignore
#     """Load dataset items.

#     Args:
#         ds_id (str): Dataset ID
#         params (Params, optional): Pagination parameters (offset and limit). Defaults to Depends().

#     Returns:
#         Page[DatasetExplorer]: Dataset explorer page
#     """
#     # Load dataset
#     dataset = Dataset.find(ds_id, settings.data_dir)

#     if dataset:
#         # Get page parameters
#         params = resolve_params(params)
#         raw_params = params.to_raw_params()
#         total = dataset.num_rows

#         # Check page parameters
#         start = raw_params.offset
#         stop = min(raw_params.offset + raw_params.limit, total)
#         if start >= stop:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Invalid page parameters (start {start}, stop {stop})",
#             )

#         # Load dataset items
#         #items = dataset.get_items(raw_params.offset, raw_params.limit)
#         all_ids = dataset.get_all_ids()
#         ids = sorted(all_ids)[raw_params.offset:raw_params.offset+raw_params.limit]
#         items = dataset.read_items(ids)
#         if items:
#             # TODO --> convert CustomDatasetItem (from new API) to legacy DatasetItem
#             print("BR - items", len(items), items[0].__dict__.keys())
#             # print("BR - item", item[0])
#             ## item ex: dict_keys(['rgb_sequence', 'objects', 'id', 'split', 'sequence_name'])
#             ## need to find which parts belongs to item (here ((id, split)-->always in item), sequence_name)
#             ## (here sequence_name must be put in features)
#             ## and in which groups are others (here: objects -> objects, rgb_sequence -> views (aka media))
#             legacy_items = []
#             for item in items:
#                 # note: we could do it on item[0] only in fact
#                 groups = defaultdict(list)
#                 for tname in item.__dict__.keys():
#                     found_group = (
#                         _SchemaGroup.ITEM
#                     )  # if no matching group (-> it's not a table name), it is in ITEM
#                     for group, tnames in dataset.dataset_schema._groups.items():
#                         if tname in tnames:
#                             found_group = group
#                             break
#                     if tname not in [
#                         "id",
#                         "split",
#                     ]:  # id and split are always present, and in ITEM group
#                         groups[found_group].append(tname)

#                 # features
#                 features = {
#                     val: {
#                         "name": val,
#                         "dtype": type(item.__dict__[val]).__name__,
#                         "value": item.__dict__[val],
#                     }
#                     for val in groups[_SchemaGroup.ITEM]
#                 }

#                 # views : {"table_name": ItemView}
#                 # "https://upload.wikimedia.org/wikipedia/en/f/f0/Information_orange.svg",  # TMP fake thumbnail
#                 views = {}
#                 for val in groups[_SchemaGroup.VIEW]:
#                     if isinstance(item.__dict__[val], Image):
#                         view = {
#                             "id": val,
#                             "type": "image",
#                             "uri": item.__dict__[val].url,
#                             "thumbnail": item.__dict__[val].open(dataset.path / "media"),
#                         }
#                     elif (
#                         isinstance(item.__dict__[val], list)
#                         and len(item.__dict__[val]) > 0
#                         and isinstance(item.__dict__[val][0], SequenceFrame)
#                     ):
#                         view = {
#                             "id": val,
#                             "type": "video",  # in fact sequence frames
#                             "uri": "",
#                             "thumbnail": item.__dict__[val][0].open(dataset.path / "media")
#                         }

#                     views[val] = view

#                 legacy_item = LegacyDatasetItem(
#                     id=item.id,
#                     split=item.split,
#                     views=views,
#                     objects={},  # should not need objects here
#                     features=features,
#                     embeddings={},  # should not need embeddings here
#                 )
#                 legacy_items.append(legacy_item)

#             print("BR - leg_items", len(legacy_items), legacy_items[0].__dict__.keys())
#             # print("BR - leg_items0", legacy_items[0])
#             # Return dataset items
#             outpage = create_page(legacy_items, total=total, params=params)
#             # print("BR output page", outpage)
#             # print("BR output page0", outpage.items[0])
#             return outpage
#         raise HTTPException(
#             status_code=404,
#             detail=(
#                 f"No items found with page parameters (start {start}, "
#                 f"stop {stop}) in dataset",
#             ),
#         )
#     raise HTTPException(
#         status_code=404,
#         detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
#     )


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
        ids = sorted(all_ids)[raw_params.offset: raw_params.offset + raw_params.limit]
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


@router.get("/items/{item_id}", response_model=LegacyDatasetItem)
async def get_dataset_item(  # noqa: D417
    ds_id: str,
    item_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LegacyDatasetItem:  # type: ignore
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
        # "https://upload.wikimedia.org/wikipedia/en/f/f0/Information_orange.svg",  # TMP fake thumbnail
        views = {}
        view_type = "image"
        for view_name in groups[_SchemaGroup.VIEW]:
            view_item = getattr(item, view_name)
            if isinstance(view_item, Image):
                views[view_name] = {
                    "id": view_name,
                    # "type": "image",
                    "uri": "data/" + dataset.path.name + "/media/" + view_item.url,
                    "thumbnail": None,  # view_item.open(dataset.path / "media"),
                    "features": {
                        "width": view_item.width,
                        "height": view_item.height,
                    },
                }
            elif (
                isinstance(view_item, list)
                and len(view_item) > 0
                and isinstance(view_item[0], SequenceFrame)
            ):
                views[view_name] = [{
                    "id": view_name,
                    # "type": "video",
                    "uri": "data/" + dataset.path.name + "/media/" + frame.url,
                    # "uri": view_item[0].open(dataset.path / "media"),  # TMP!! need to give vid..?
                    "thumbnail": None,  # frame.open(dataset.path / "media"),
                    "features": {
                        "width": frame.width,
                        "height": frame.height,
                    },
                } for frame in view_item]
                view_type = "video"

        # objects
        objects = []
        for obj_group in groups[_SchemaGroup.OBJECT]:
            objects.extend(
                [
                    {
                        "id": obj.id,
                        "item_id": obj.item_id,
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

        legacy_item = LegacyDatasetItem(
            id=item.id,
            type=view_type,
            split=item.split,
            views=views,
            objects=objects,
            features=features,
            embeddings={},  # should not need embeddings here
        )

        # Return dataset item
        if legacy_item:
            return legacy_item
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
        item = dataset.get_item(
            item_id,
            select_tables_per_group={_SchemaGroup.EMBEDDING: [model_id]},
        )

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
