from typing import Dict, Type
from lancedb.pydantic import LanceModel
from .image import Image
from .video import Video
from .sequence_frame import SequenceFrame
from .item import Item
from .point_cloud import PointCloud
from .embedding import Embedding


_TYPE_REGISTRY: Dict[str, Type[LanceModel]] = {
    "Image": Image,
    "Video": Video,
    "SequenceFrame": SequenceFrame,
    "Item": Item,
    "PointCloud": PointCloud,
    "Embedding": Embedding
}
