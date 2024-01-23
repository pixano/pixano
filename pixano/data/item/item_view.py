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

from pathlib import Path
from typing import Optional

import pyarrow as pa
from pydantic import BaseModel
from s3path import S3Path

from pixano.core import Image, is_image_type
from pixano.data.item.item_feature import ItemFeature


class ItemView(BaseModel):
    """View type for DatasetItem

    Attributes:
        id (str): View ID
        type (str): View type ("image", "video", "point_cloud")
        url (str): View URI
        thumbnail (str, optional): View thumbnail as base 64 URL
        frame_number (int, optional): View frame number
        total_frames (int, optional): View total frames
        features (dict[str, ItemFeature], optional): View features
    """

    id: str
    type: str
    uri: str
    thumbnail: Optional[str] = None
    frame_number: Optional[int] = None
    total_frames: Optional[int] = None
    features: Optional[dict[str, ItemFeature]] = None

    @staticmethod
    def from_pyarrow(
        table: pa.Table,
        schema: pa.schema,
        media_dir: Path,
        media_features: bool = False,
    ) -> dict[str, "ItemView"]:
        """Create dictionary of ItemView from PyArrow Table

        Args:
            table (dict[str, Any]): PyArrow table
            schema (pa.schema): PyArrow schema
            media_dir (Path): Dataset media directory
            media_features (bool, optional): Load media features like image width and height (slow for large item batches)

        Returns:
            dict[ItemView]: Dictionary of ItemView
        """

        # NOTE: Potential change to flattened view fields with one row per view
        item = table.to_pylist()[0] if len(table.to_pylist()) > 0 else None
        views = {}

        # Iterate on fields
        for field in schema:
            # Image
            if is_image_type(field.type):
                if item is not None:
                    im = (
                        item[field.name]
                        if isinstance(item[field.name], Image)
                        else Image.from_dict(item[field.name])
                    )
                    im.uri_prefix = media_dir.absolute().as_uri()
                    api_uri = (
                        (media_dir / im.uri).get_presigned_url()
                        if isinstance(media_dir, S3Path)
                        else f"data/{media_dir.parent.name}/media/{im.uri}"
                    )
                    image_view = ItemView(
                        id=field.name,
                        type="image",
                        uri=api_uri,
                        thumbnail=im.preview_url,
                    )
                    image_view.features = {}
                    if media_features:
                        image_view.features["width"] = ItemFeature(
                            name="width",
                            dtype="int",
                            value=im.width,
                        )

                        image_view.features["height"] = ItemFeature(
                            name="height",
                            dtype="int",
                            value=im.height,
                        )
                    views[field.name] = image_view
                else:
                    views[field.name] = ItemView(id=field.name, type="image", uri="")

            # NOTE: Future support for videos and 3D point clouds

        return views
