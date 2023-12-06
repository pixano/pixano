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
from urllib.parse import urlparse

import pyarrow as pa
from pydantic import BaseModel

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
        table: pa.Table, schema: pa.schema, media_dir: Path
    ) -> dict[str, "ItemView"]:
        """Create dictionary of ItemView from PyArrow Table

        Args:
            table (dict[str, Any]): PyArrow table
            schema (pa.schema): PyArrow schema
            media_dir (Path): Dataset media directory

        Returns:
            dict[ItemView]: Dictionary of ItemView
        """

        # TODO: Flattened view fields with one row per view?
        item = table.to_pylist()[0]
        views = {}

        # Iterate on fields
        for field in schema:
            # Image
            if is_image_type(field.type):
                im = (
                    item["image"]
                    if isinstance(item["image"], Image)
                    else Image.from_dict(item["image"])
                )
                im.uri_prefix = media_dir.absolute().as_uri()
                image_view = ItemView(
                    id=field.name,
                    type="image",
                    uri=f"data/{media_dir.parent.name}/media/{im.uri}"
                    if urlparse(im.uri).scheme == ""
                    else im.uri,
                    thumbnail=im.preview_url,
                )
                image_view.features = {}
                image_view.features["width"] = ItemFeature(
                    name="width",
                    dtype="number",
                    value=im.width,
                )

                image_view.features["height"] = ItemFeature(
                    name="height",
                    dtype="number",
                    value=im.height,
                )
                views[field.name] = image_view
            # TODO: Video, Point cloud

        return views
