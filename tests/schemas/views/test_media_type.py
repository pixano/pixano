# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.schemas import (
    MEDIA_TYPES,
    CalibratedImage,
    CalibratedPointCloud,
    Image,
    PointCloud,
    Record,
    SequenceFrame,
    Text,
    Video,
    media_type_of,
)


class TestMediaTypeOf:
    """The vocabulary a user chooses a job's media from, and the embeddings health counts in."""

    @pytest.mark.parametrize(
        ("schema", "expected"),
        [
            (Image, "image"),
            (CalibratedImage, "image"),
            (Video, "video"),
            (PointCloud, "point_cloud"),
            (CalibratedPointCloud, "point_cloud"),
            (Text, "text"),
            (Record, None),
        ],
    )
    def test_names_the_media_a_schema_holds(self, schema: type, expected: str | None) -> None:
        assert media_type_of(schema) == expected

    def test_a_video_frame_belongs_to_its_video(self) -> None:
        """An image to the schemas, but choosing images on a video dataset must not cover every frame."""
        assert media_type_of(SequenceFrame) == "video"

    def test_the_vocabulary_is_closed(self) -> None:
        assert set(MEDIA_TYPES) == {"image", "video", "point_cloud", "text"}
