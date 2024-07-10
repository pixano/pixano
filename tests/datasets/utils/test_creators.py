# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.features import (
    AnnotationRef,
    BaseType,
    BBox,
    BBox3D,
    CamCalibration,
    CompressedRLE,
    EmbeddingRef,
    EntityRef,
    Image,
    ItemRef,
    KeyPoints,
    KeyPoints3D,
    NDArrayFloat,
    PointCloud,
    SchemaRef,
    SequenceFrame,
    Track,
    Tracklet,
    TrackRef,
    Video,
    ViewRef,
    create_annotation_ref,
    create_bbox,
    create_bbox3d,
    create_cam_calibration,
    create_compressed_rle,
    create_embedding_ref,
    create_entity_ref,
    create_image,
    create_item_ref,
    create_keypoints,
    create_keypoints3d,
    create_ndarray_float,
    create_point_cloud,
    create_schema_ref,
    create_sequence_frame,
    create_track,
    create_track_ref,
    create_tracklet,
    create_video,
    create_view_ref,
)
from pixano.datasets.features.schemas.annotations.camcalibration import BaseIntrinsics, Extrinsics, Intrinsics
from pixano.datasets.features.schemas.base_schema import BaseSchema
from pixano.datasets.utils.creators import create_pixano_object, create_row


def test_create_row_image():
    row = create_row(Image, url="image.jpg", width=100, height=100, format="jpg")
    assert row == create_image(url="image.jpg", width=100, height=100, format="jpg")


def test_create_row_video():
    row = create_row(Video, url="video.mp4", width=100, height=100, format="mp4", duration=10, fps=30, num_frames=300)
    assert row == create_video(
        url="video.mp4", width=100, height=100, format="mp4", duration=10, fps=30, num_frames=300
    )


def test_create_row_sequence_frame():
    row = create_row(SequenceFrame, url="frame.jpg", width=100, height=100, format="jpg", frame_index=0, timestamp=0.0)
    assert row == create_sequence_frame(
        url="frame.jpg", width=100, height=100, format="jpg", frame_index=0, timestamp=0.0
    )


def test_create_row_tracklet():
    row = create_row(Tracklet, start_timestamp=0.0, end_timestamp=1.0)
    assert row == create_tracklet(start_timestamp=0.0, end_timestamp=1.0)


def test_create_row_track():
    row = create_row(Track, name="track1")
    assert row == create_track(name="track1")


def test_create_row_bbox():
    row = create_row(BBox, coords=[0.4, 0.5, 0.1, 0.1], format="xywh", is_normalized=True)
    assert row == create_bbox(coords=[0.4, 0.5, 0.1, 0.1], format="xywh", is_normalized=True)


def test_create_row_bbox3d():
    row = create_row(
        BBox3D, coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], format="xyzwhd", is_normalized=True, heading=[0.0, 0.0, 0.0]
    )
    assert row == create_bbox3d(
        coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], format="xyzwhd", is_normalized=True, heading=[0.0, 0.0, 0.0]
    )


def test_create_row_cam_calibration():
    row = create_row(
        CamCalibration,
        type="perspective",
        base_intrinsics=BaseIntrinsics(cx_offset_px=0, cy_offset_px=0, img_height_px=0, img_width_px=0),
        extrinsics=Extrinsics(pos_x_m=0, pos_y_m=0, pos_z_m=0, rot_x_deg=0, rot_z1_deg=0, rot_z2_deg=0),
        intrinsics=Intrinsics(c1=0, c2=0, c3=0, c4=0, pixel_aspect_ratio=0),
    )
    assert row == create_cam_calibration(
        type="perspective",
        base_intrinsics=BaseIntrinsics(cx_offset_px=0, cy_offset_px=0, img_height_px=0, img_width_px=0),
        extrinsics=Extrinsics(pos_x_m=0, pos_y_m=0, pos_z_m=0, rot_x_deg=0, rot_z1_deg=0, rot_z2_deg=0),
        intrinsics=Intrinsics(c1=0, c2=0, c3=0, c4=0, pixel_aspect_ratio=0),
    )


def test_create_row_compressed_rle():
    row = create_row(CompressedRLE, size=[100], counts=b"1")
    assert row == create_compressed_rle(size=[100], counts=b"1")


def test_create_row_keypoints():
    row = create_row(KeyPoints, template_id="template1", coords=[0.4, 0.5, 0.1, 0.1], states=["visible", "hidden"])
    assert row == create_keypoints(template_id="template1", coords=[0.4, 0.5, 0.1, 0.1], states=["visible", "hidden"])


def test_create_row_keypoints3d():
    row = create_row(
        KeyPoints3D, template_id="template1", coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], states=["visible", "hidden"]
    )
    assert row == create_keypoints3d(
        template_id="template1", coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], states=["visible", "hidden"]
    )


def test_create_point_cloud():
    row = create_row(PointCloud, url="point_cloud.ply")
    assert row == create_point_cloud(url="point_cloud.ply")


def test_create_row_custom_schema():
    class CustomSchema(BaseSchema):
        name: str

    obj = create_row(CustomSchema, name="custom")
    assert obj == CustomSchema(name="custom")


def test_create_row_unsupported():
    class InvalidSchema:
        pass

    with pytest.raises(
        ValueError,
        match=(
            "Schema <class 'tests.datasets.utils.test_creators.test_create_row_unsupported.<locals>.InvalidSchema'> "
            "is not a base schema."
        ),
    ):
        create_row(InvalidSchema)


def test_create_pixano_object_ndarray_float():
    ndarray_float = create_pixano_object(NDArrayFloat, values=[1.0, 2.0, 3.0], shape=[3])
    assert ndarray_float == create_ndarray_float(values=[1.0, 2.0, 3.0], shape=[3])


def test_create_pixano_object_embedding_ref():
    embedding_ref = create_pixano_object(EmbeddingRef, id="embedding1", name="embedding")
    assert embedding_ref == create_embedding_ref(id="embedding1", name="embedding")


def test_create_pixano_object_annotation_ref():
    annotation_ref = create_pixano_object(AnnotationRef, id="annotation1", name="annotation")
    assert annotation_ref == create_annotation_ref(id="annotation1", name="annotation")


def test_create_pixano_object_entity_ref():
    entity_ref = create_pixano_object(EntityRef, id="entity1", name="entity")
    assert entity_ref == create_entity_ref(id="entity1", name="entity")


def test_create_pixano_object_item_ref():
    item_ref = create_pixano_object(ItemRef, id="item1")
    assert item_ref == create_item_ref(id="item1")


def test_create_pixano_object_schema_ref():
    schema_ref = create_pixano_object(SchemaRef, id="schema1", name="schema")
    assert schema_ref == create_schema_ref(id="schema1", name="schema")


def test_create_pixano_object_track_ref():
    track_ref = create_pixano_object(TrackRef, id="track1", name="track")
    assert track_ref == create_track_ref(id="track1", name="track")


def test_create_pixano_object_view_ref():
    view_ref = create_pixano_object(ViewRef, id="view1", name="view")
    assert view_ref == create_view_ref(id="view1", name="view")

def test_create_pixano_object_custom_type():
    class CustomType(BaseType):
        name: str

    assert create_pixano_object(CustomType, name="custom") == CustomType(name="custom")


def test_create_pixano_object_unsupported():
    with pytest.raises(ValueError, match="Type <class 'int'> not supported."):
        create_pixano_object(int)
