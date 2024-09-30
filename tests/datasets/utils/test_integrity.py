# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.utils.integrity import (
    IntegrityCheck,
    check_dataset_integrity,
    check_table_integrity,
    get_integry_checks_from_schemas,
)
from pixano.features import EntityRef, ItemRef, SourceRef, ViewRef


def test_get_integrity_checks_from_schemas(two_difficult_bboxes_from_dataset_multiview_tracking_and_image):
    checks = get_integry_checks_from_schemas(two_difficult_bboxes_from_dataset_multiview_tracking_and_image, "bbox")
    check_ids = [check[0] for check in checks[0]]
    assert checks == [
        [
            (check_ids[0], "bbox", "bbox_image_0", "id", "bbox_image_0"),
            (check_ids[1], "bbox", "bbox_image_1", "id", "bbox_image_1"),
        ],
        [
            (check_ids[0], "bbox", "bbox_image_0", "id", "bbox_image_0"),
            (check_ids[1], "bbox", "bbox_image_1", "id", "bbox_image_1"),
        ],
        [
            (check_ids[0], "bbox", "bbox_image_0", "item_ref", ItemRef(name="item", id="0")),
            (check_ids[0], "bbox", "bbox_image_0", "view_ref", ViewRef(name="image", id="image_0")),
            (
                check_ids[0],
                "bbox",
                "bbox_image_0",
                "entity_ref",
                EntityRef(name="entity_image", id="entity_image_0"),
            ),
            (check_ids[0], "bbox", "bbox_image_0", "source_ref", SourceRef(name="source", id="source_0")),
            (check_ids[1], "bbox", "bbox_image_1", "item_ref", ItemRef(name="item", id="1")),
            (check_ids[1], "bbox", "bbox_image_1", "view_ref", ViewRef(name="image", id="image_1")),
            (
                check_ids[1],
                "bbox",
                "bbox_image_1",
                "entity_ref",
                EntityRef(name="entity_image", id="entity_image_1"),
            ),
            (check_ids[1], "bbox", "bbox_image_1", "source_ref", SourceRef(name="source", id="source_1")),
        ],
        [
            (check_ids[0], "bbox", "bbox_image_0", "item_ref", ItemRef(name="item", id="0")),
            (check_ids[0], "bbox", "bbox_image_0", "view_ref", ViewRef(name="image", id="image_0")),
            (
                check_ids[0],
                "bbox",
                "bbox_image_0",
                "entity_ref",
                EntityRef(name="entity_image", id="entity_image_0"),
            ),
            (check_ids[0], "bbox", "bbox_image_0", "source_ref", SourceRef(name="source", id="source_0")),
            (check_ids[1], "bbox", "bbox_image_1", "item_ref", ItemRef(name="item", id="1")),
            (check_ids[1], "bbox", "bbox_image_1", "view_ref", ViewRef(name="image", id="image_1")),
            (
                check_ids[1],
                "bbox",
                "bbox_image_1",
                "entity_ref",
                EntityRef(name="entity_image", id="entity_image_1"),
            ),
            (check_ids[1], "bbox", "bbox_image_1", "source_ref", SourceRef(name="source", id="source_1")),
        ],
        [
            (check_ids[0], "bbox", "bbox_image_0", "item_ref", ItemRef(name="item", id="0")),
            (check_ids[0], "bbox", "bbox_image_0", "view_ref", ViewRef(name="image", id="image_0")),
            (
                check_ids[0],
                "bbox",
                "bbox_image_0",
                "entity_ref",
                EntityRef(name="entity_image", id="entity_image_0"),
            ),
            (check_ids[0], "bbox", "bbox_image_0", "source_ref", SourceRef(name="source", id="source_0")),
            (check_ids[1], "bbox", "bbox_image_1", "item_ref", ItemRef(name="item", id="1")),
            (check_ids[1], "bbox", "bbox_image_1", "view_ref", ViewRef(name="image", id="image_1")),
            (
                check_ids[1],
                "bbox",
                "bbox_image_1",
                "entity_ref",
                EntityRef(name="entity_image", id="entity_image_1"),
            ),
            (check_ids[1], "bbox", "bbox_image_1", "source_ref", SourceRef(name="source", id="source_1")),
        ],
    ]


def test_check_table_integrity_defined_id(
    dataset_multi_view_tracking_and_image, two_difficult_bboxes_from_dataset_multiview_tracking_and_image
):
    table = dataset_multi_view_tracking_and_image.open_table("bbox_image")
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, None)
    assert errors == {}

    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[0].id = ""
    bboxes[1].id = "unique_id"
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes)
    assert len(errors) == 1
    assert list(errors.values())[0] == (IntegrityCheck.DEFINED_ID, "bbox_image", "id", "", "")


def test_check_table_integrity_defined_ref_ignore(
    dataset_multi_view_tracking_and_image, two_difficult_bboxes_from_dataset_multiview_tracking_and_image
):
    table = dataset_multi_view_tracking_and_image.open_table("bbox_image")
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, None)
    assert errors == {}

    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[0].id = ""
    bboxes[1].id = "unique_id"
    errors = check_table_integrity(
        table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes, ignore_checks=[IntegrityCheck.DEFINED_ID]
    )
    assert errors == {}


def test_check_table_integrity_unique_id(
    dataset_multi_view_tracking_and_image, two_difficult_bboxes_from_dataset_multiview_tracking_and_image
):
    # Test no error
    table = dataset_multi_view_tracking_and_image.open_table("bbox_image")
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, None)
    assert errors == {}

    # Test one error with updating is False
    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[1].id = "unique_id"
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes)
    assert len(errors) == 1
    assert list(errors.values())[0] == (IntegrityCheck.UNIQUE_ID, "bbox_image", "id", "bbox_image_0", "bbox_image_0")

    # Test updating is True
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes, True)
    assert errors == {}

    # Test two errors
    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[0].id = "not_unique_id"
    bboxes[1].id = "not_unique_id"
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes)
    assert len(errors) == 2
    assert list(errors.values()) == [
        (IntegrityCheck.UNIQUE_ID, "bbox_image", "id", "not_unique_id", "not_unique_id"),
        (IntegrityCheck.UNIQUE_ID, "bbox_image", "id", "not_unique_id", "not_unique_id"),
    ]


def test_check_table_integrity_ref_name(
    dataset_multi_view_tracking_and_image, two_difficult_bboxes_from_dataset_multiview_tracking_and_image
):
    table = dataset_multi_view_tracking_and_image.open_table("bbox_image")
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, None)
    assert errors == {}

    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[0].id = "unique_id_0"
    bboxes[1].id = "unique_id_1"
    bboxes[0].view_ref.name = "not_image"
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes)
    assert len(errors) == 1
    assert list(errors.values())[0] == (
        IntegrityCheck.REF_NAME,
        "bbox_image",
        "view_ref",
        "unique_id_0",
        bboxes[0].view_ref,
    )


@pytest.mark.parametrize("ref_attribute, ref_name", (("view_ref", "entity_image"), ("entity_ref", "image")))
def test_check_table_integrity_ref_type(
    dataset_multi_view_tracking_and_image,
    two_difficult_bboxes_from_dataset_multiview_tracking_and_image,
    ref_attribute,
    ref_name,
):
    table = dataset_multi_view_tracking_and_image.open_table("bbox_image")
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, None)
    assert errors == {}

    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[0].id = "unique_id_0"
    bboxes[1].id = "unique_id_1"
    ref_attr = getattr(bboxes[0], ref_attribute)
    ref_attr.name = ref_name
    setattr(bboxes[0], ref_attribute, ref_attr)
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes)
    assert len(errors) == 1
    assert list(errors.values())[0] == (
        IntegrityCheck.REF_TYPE,
        "bbox_image",
        ref_attribute,
        "unique_id_0",
        ref_attr,
    )


def test_check_table_integrity_ref_id(
    dataset_multi_view_tracking_and_image,
    two_difficult_bboxes_from_dataset_multiview_tracking_and_image,
):
    table = dataset_multi_view_tracking_and_image.open_table("bbox_image")
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, None)
    assert errors == {}

    bboxes = [bbox.model_copy(deep=True) for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image]
    bboxes[0].id = "unique_id_0"
    bboxes[1].id = "unique_id_1"
    bboxes[0].view_ref.id = "not_image_id"
    bboxes[1].source_ref.id = "not_source_id"
    errors = check_table_integrity(table, "bbox_image", dataset_multi_view_tracking_and_image, bboxes)
    assert len(errors) == 2
    assert list(errors.values()) == [
        (
            IntegrityCheck.REF_ID,
            "bbox_image",
            "view_ref",
            "unique_id_0",
            bboxes[0].view_ref,
        ),
        (
            IntegrityCheck.REF_ID,
            "bbox_image",
            "source_ref",
            "unique_id_1",
            bboxes[1].source_ref,
        ),
    ]


def test_check_dataset_integrity(
    dataset_multi_view_tracking_and_image_copy,
    two_difficult_bboxes_from_dataset_multiview_tracking_and_image,
    two_image_entities_from_dataset_multiview_tracking_and_image,
):
    errors = check_dataset_integrity(dataset_multi_view_tracking_and_image_copy)
    assert errors == {}

    bboxes = [
        dataset_multi_view_tracking_and_image_copy.schema.schemas["bbox_image"].model_validate(bbox.model_dump())
        for bbox in two_difficult_bboxes_from_dataset_multiview_tracking_and_image
    ]
    bboxes[0].id = "unique_id_0"
    bboxes[1].id = "unique_id_1"
    bboxes[0].entity_ref.name = "not_entity_image"
    bboxes[1].source_ref.id = "not_source_id"

    entities = [
        dataset_multi_view_tracking_and_image_copy.schema.schemas["entity_image"].model_validate(entity.model_dump())
        for entity in two_image_entities_from_dataset_multiview_tracking_and_image
    ]
    entities[0].id = "unique_id_0"
    entities[1].id = "unique_id_1"
    entities[0].view_ref.name = "not_image"
    entities[1].item_ref.id = "not_item_id"

    bbox_table = dataset_multi_view_tracking_and_image_copy.open_table("bbox_image")
    bbox_table.add(bboxes)
    entity_table = dataset_multi_view_tracking_and_image_copy.open_table("entity_image")
    entity_table.add(entities)

    errors = check_dataset_integrity(dataset_multi_view_tracking_and_image_copy)

    assert len(errors) == 4
    assert list(errors.values()) == [
        (IntegrityCheck.REF_NAME, "entity_image", "view_ref", "unique_id_0", ViewRef(name="not_image", id="image_0")),
        (IntegrityCheck.REF_ID, "entity_image", "item_ref", "unique_id_1", ItemRef(name="item", id="not_item_id")),
        (
            IntegrityCheck.REF_NAME,
            "bbox_image",
            "entity_ref",
            "unique_id_0",
            EntityRef(name="not_entity_image", id="entity_image_0"),
        ),
        (
            IntegrityCheck.REF_ID,
            "bbox_image",
            "source_ref",
            "unique_id_1",
            SourceRef(name="source", id="not_source_id"),
        ),
    ]
