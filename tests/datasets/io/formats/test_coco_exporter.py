# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

import pytest

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.io import export_dataset
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, Image, Record


@pytest.mark.parametrize(
    "box_format,is_normalized,coords",
    [
        pytest.param("xyxy", True, [0.1, 0.2, 0.4, 0.6], id="normalized-xyxy"),
        pytest.param("xyxy", False, [10.0, 40.0, 40.0, 120.0], id="pixel-xyxy"),
        pytest.param("xywh", True, [0.1, 0.2, 0.3, 0.4], id="normalized-xywh"),
        pytest.param("xywh", False, [10.0, 40.0, 30.0, 80.0], id="pixel-xywh"),
    ],
)
def test_export_bbox_uses_pixel_xywh_without_changing_source(
    tmp_path: Path, box_format: str, is_normalized: bool, coords: list[float]
):
    dataset = Dataset.create(
        tmp_path / "dataset",
        DatasetInfo(
            name="boxes",
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        ),
    )
    dataset.add_records(
        {
            "records": [Record(id="record", split="train")],
            "images": [
                Image(
                    id="image",
                    record_id="record",
                    logical_name="image",
                    uri="https://example.com/image.jpg",
                    width=100,
                    height=200,
                    format="JPEG",
                )
            ],
            "entities": [Entity(id="entity", record_id="record")],
            "bboxes": [
                BBox(
                    id="bbox",
                    record_id="record",
                    view_id="image",
                    entity_id="entity",
                    coords=coords,
                    format=box_format,
                    is_normalized=is_normalized,
                )
            ],
        }
    )
    original = dataset.get_data("bboxes")[0].model_dump()

    exported = export_dataset(dataset, tmp_path / "exported", format="coco", media="uris")

    document = json.loads((exported / "instances_train.json").read_text())
    assert len(document["annotations"]) == 1
    annotation = document["annotations"][0]
    assert annotation["bbox"] == pytest.approx([10.0, 40.0, 30.0, 80.0])
    assert annotation["area"] == pytest.approx(2400.0)
    assert Dataset(dataset.path).get_data("bboxes")[0].model_dump() == original
