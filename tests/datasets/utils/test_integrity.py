# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.utils.integrity import (
    IntegrityCheck,
    check_dataset_integrity,
    check_table_integrity,
    get_integry_checks_from_schemas,
)


def test_get_integrity_checks_from_schemas(dataset_multi_view_tracking_and_image):
    bboxes = dataset_multi_view_tracking_and_image.get_data("bboxes_video", limit=2)

    checks = get_integry_checks_from_schemas(bboxes, "bboxes_video")
    assert len(checks[IntegrityCheck.DEFINED_ID.value]) == 2
    assert len(checks[IntegrityCheck.UNIQUE_ID.value]) == 2

    fk_field_names = {field_name for _, _, _, field_name, _ in checks[IntegrityCheck.FK_ID.value]}
    assert fk_field_names == {
        "entity_dynamic_state_id",
        "entity_id",
        "frame_id",
        "record_id",
        "tracklet_id",
        "view_id",
    }


def test_check_table_integrity_detects_missing_and_duplicate_ids(dataset_multi_view_tracking_and_image):
    bboxes = [
        bbox.model_copy(deep=True) for bbox in dataset_multi_view_tracking_and_image.get_data("bboxes_video", limit=2)
    ]

    bboxes[0].id = ""
    bboxes[1].id = "duplicate"
    errors = check_table_integrity("bboxes_video", dataset_multi_view_tracking_and_image, bboxes)
    assert (IntegrityCheck.DEFINED_ID, "bboxes_video", "id", "", "") in errors

    bboxes = [
        bbox.model_copy(deep=True) for bbox in dataset_multi_view_tracking_and_image.get_data("bboxes_video", limit=2)
    ]
    bboxes[0].id = "duplicate"
    bboxes[1].id = "duplicate"
    errors = check_table_integrity("bboxes_video", dataset_multi_view_tracking_and_image, bboxes)
    assert errors == [(IntegrityCheck.UNIQUE_ID, "bboxes_video", "id", "duplicate", "duplicate")]


def test_check_table_integrity_detects_invalid_foreign_keys(dataset_multi_view_tracking_and_image):
    bboxes = [
        bbox.model_copy(deep=True) for bbox in dataset_multi_view_tracking_and_image.get_data("bboxes_video", limit=1)
    ]
    bboxes[0].id = "invalid_bbox"
    bboxes[0].entity_id = "missing_entity"
    bboxes[0].frame_id = "missing_frame"

    errors = check_table_integrity("bboxes_video", dataset_multi_view_tracking_and_image, bboxes)
    assert errors == [
        (IntegrityCheck.FK_ID, "bboxes_video", "entity_id", "invalid_bbox", "missing_entity"),
        (IntegrityCheck.FK_ID, "bboxes_video", "frame_id", "invalid_bbox", "missing_frame"),
    ]


def test_check_dataset_integrity_reports_invalid_rows(dataset_multi_view_tracking_and_image_copy):
    bbox = dataset_multi_view_tracking_and_image_copy.get_data("bboxes_video", limit=1)[0].model_copy(deep=True)
    bbox.id = "corrupt_bbox"
    bbox.entity_id = "missing_entity"

    dataset_multi_view_tracking_and_image_copy.open_table("bboxes_video").add([bbox])

    errors = check_dataset_integrity(dataset_multi_view_tracking_and_image_copy)
    assert (IntegrityCheck.FK_ID, "bboxes_video", "entity_id", "corrupt_bbox", "missing_entity") in errors
