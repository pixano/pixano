# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json

import pytest

from pixano.features import (
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
    create_tracklet,
    create_video,
    create_view_ref,
)
from pixano.features.schemas.annotations.camcalibration import BaseIntrinsics, Extrinsics, Intrinsics
from pixano.features.schemas.base_schema import BaseSchema
from pixano.features.schemas.source import create_source
from pixano.features.types.schema_reference import SourceRef, create_source_ref
from pixano.features.utils.creators import create_instance_of_pixano_type, create_instance_of_schema


def test_create_row_image():
    row = create_instance_of_schema(Image, url="image.jpg", width=100, height=100, format="jpg")
    assert row.model_dump(exclude_timestamps=True) == create_image(
        url="image.jpg", width=100, height=100, format="jpg"
    ).model_dump(exclude_timestamps=True)


def test_create_row_video():
    row = create_instance_of_schema(
        Video, url="video.mp4", width=100, height=100, format="mp4", duration=10, fps=30, num_frames=300
    )
    assert row.model_dump(exclude_timestamps=True) == create_video(
        url="video.mp4", width=100, height=100, format="mp4", duration=10, fps=30, num_frames=300
    ).model_dump(exclude_timestamps=True)


def test_create_row_sequence_frame():
    row = create_instance_of_schema(
        SequenceFrame, url="frame.jpg", width=100, height=100, format="jpg", frame_index=0, timestamp=0.0
    )
    assert row.model_dump(exclude_timestamps=True) == create_sequence_frame(
        url="frame.jpg", width=100, height=100, format="jpg", frame_index=0, timestamp=0.0
    ).model_dump(exclude_timestamps=True)


def test_create_row_tracklet():
    row = create_instance_of_schema(Tracklet, start_timestamp=0.0, end_timestamp=1.0)
    assert row.model_dump(exclude_timestamps=True) == create_tracklet(
        start_timestamp=0.0, end_timestamp=1.0
    ).model_dump(exclude_timestamps=True)


def test_create_row_track():
    row = create_instance_of_schema(Track, name="track1")
    assert row.model_dump(exclude_timestamps=True) == create_track(name="track1").model_dump(exclude_timestamps=True)


def test_create_row_bbox():
    row = create_instance_of_schema(BBox, coords=[0.4, 0.5, 0.1, 0.1], format="xywh", is_normalized=True)
    assert row.model_dump(exclude_timestamps=True) == create_bbox(
        coords=[0.4, 0.5, 0.1, 0.1], format="xywh", is_normalized=True
    ).model_dump(exclude_timestamps=True)


def test_create_row_bbox3d():
    row = create_instance_of_schema(
        BBox3D, coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], format="xyzwhd", is_normalized=True, heading=[0.0, 0.0, 0.0]
    )
    assert row.model_dump(exclude_timestamps=True) == create_bbox3d(
        coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], format="xyzwhd", is_normalized=True, heading=[0.0, 0.0, 0.0]
    ).model_dump(exclude_timestamps=True)


def test_create_row_cam_calibration():
    row = create_instance_of_schema(
        CamCalibration,
        type="perspective",
        base_intrinsics=BaseIntrinsics(cx_offset_px=0, cy_offset_px=0, img_height_px=0, img_width_px=0),
        extrinsics=Extrinsics(pos_x_m=0, pos_y_m=0, pos_z_m=0, rot_x_deg=0, rot_z1_deg=0, rot_z2_deg=0),
        intrinsics=Intrinsics(c1=0, c2=0, c3=0, c4=0, pixel_aspect_ratio=0),
    )
    assert row.model_dump(exclude_timestamps=True) == create_cam_calibration(
        type="perspective",
        base_intrinsics=BaseIntrinsics(cx_offset_px=0, cy_offset_px=0, img_height_px=0, img_width_px=0),
        extrinsics=Extrinsics(pos_x_m=0, pos_y_m=0, pos_z_m=0, rot_x_deg=0, rot_z1_deg=0, rot_z2_deg=0),
        intrinsics=Intrinsics(c1=0, c2=0, c3=0, c4=0, pixel_aspect_ratio=0),
    ).model_dump(exclude_timestamps=True)


def test_create_row_compressed_rle():
    row = create_instance_of_schema(CompressedRLE, size=[100], counts=b"1")
    assert row.model_dump(exclude_timestamps=True) == create_compressed_rle(size=[100], counts=b"1").model_dump(
        exclude_timestamps=True
    )


def test_create_row_keypoints():
    row = create_instance_of_schema(
        KeyPoints, template_id="template1", coords=[0.4, 0.5, 0.1, 0.1], states=["visible", "hidden"]
    )
    assert row.model_dump(exclude_timestamps=True) == create_keypoints(
        template_id="template1", coords=[0.4, 0.5, 0.1, 0.1], states=["visible", "hidden"]
    ).model_dump(exclude_timestamps=True)


def test_create_row_keypoints3d():
    row = create_instance_of_schema(
        KeyPoints3D, template_id="template1", coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], states=["visible", "hidden"]
    )
    assert row.model_dump(exclude_timestamps=True) == create_keypoints3d(
        template_id="template1", coords=[0.4, 0.5, 0.1, 0.1, 0.2, 0.3], states=["visible", "hidden"]
    ).model_dump(exclude_timestamps=True)


def test_create_point_cloud():
    row = create_instance_of_schema(PointCloud, url="point_cloud.ply")
    assert row.model_dump(exclude_timestamps=True) == create_point_cloud(url="point_cloud.ply").model_dump(
        exclude_timestamps=True
    )


def test_create_row_custom_schema():
    class CustomSchema(BaseSchema):
        name: str

    obj = create_instance_of_schema(CustomSchema, name="custom")
    assert obj.model_dump(exclude_timestamps=True) == CustomSchema(name="custom").model_dump(exclude_timestamps=True)


def test_create_row_unsupported():
    class InvalidSchema:
        pass

    with pytest.raises(
        ValueError,
        match=(
            "Schema <class 'tests.features.utils.test_creators.test_create_row_unsupported.<locals>.InvalidSchema'> "
            "is not a base schema."
        ),
    ):
        create_instance_of_schema(InvalidSchema)


def test_create_pixano_object_ndarray_float():
    ndarray_float = create_instance_of_pixano_type(NDArrayFloat, values=[1.0, 2.0, 3.0], shape=[3])
    assert ndarray_float == create_ndarray_float(values=[1.0, 2.0, 3.0], shape=[3])


def test_create_pixano_object_embedding_ref():
    embedding_ref = create_instance_of_pixano_type(EmbeddingRef, id="embedding1", name="embedding")
    assert embedding_ref == create_embedding_ref(id="embedding1", name="embedding")


def test_create_pixano_object_annotation_ref():
    annotation_ref = create_instance_of_pixano_type(AnnotationRef, id="annotation1", name="annotation")
    assert annotation_ref == create_annotation_ref(id="annotation1", name="annotation")


def test_create_pixano_object_entity_ref():
    entity_ref = create_instance_of_pixano_type(EntityRef, id="entity1", name="entity")
    assert entity_ref == create_entity_ref(id="entity1", name="entity")


def test_create_pixano_object_item_ref():
    item_ref = create_instance_of_pixano_type(ItemRef, id="item1")
    assert item_ref == create_item_ref(id="item1")


def test_create_pixano_object_schema_ref():
    schema_ref = create_instance_of_pixano_type(SchemaRef, id="schema1", name="schema")
    assert schema_ref == create_schema_ref(id="schema1", name="schema")


def test_create_pixano_object_source_ref():
    schema_ref = create_instance_of_pixano_type(SourceRef, id="source1")
    assert schema_ref == create_source_ref(id="source1")


def test_create_pixano_object_view_ref():
    view_ref = create_instance_of_pixano_type(ViewRef, id="view1", name="view")
    assert view_ref == create_view_ref(id="view1", name="view")


def test_create_pixano_object_custom_type():
    class CustomType(BaseType):
        name: str

    assert create_instance_of_pixano_type(CustomType, name="custom") == CustomType(name="custom")


def test_create_pixano_object_unsupported():
    with pytest.raises(ValueError, match="Type <class 'int'> not supported."):
        create_instance_of_pixano_type(int)
