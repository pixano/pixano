# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The API facing a masks table another process gave the dataset.

A job that writes masks adds the `masks` table to a dataset built without one, while the API has
the dataset open. The API must serve the job's masks from that table, not create a second one of
its own — which would rewrite `info.json` — when a person opens a record. And when the API created
the table first, because a record was opened before the job wrote, the worker must find it.
"""

import logging
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import BBox, CompressedRLE, Entity, Image, Record


DATASET_ID = "mask_table_added_elsewhere"
BASE = f"/datasets/{DATASET_ID}"
MASK_SLOT = "mask"
MASK_TABLE = "masks"
# Non-square, so that a swapped height and width shows.
IMAGE_HEIGHT = 48
IMAGE_WIDTH = 64
# The warning `BaseService.resolve_table` logs when it creates a missing table.
API_CREATION_LOG = "Auto-creating"


@pytest.fixture
def dataset() -> Dataset:
    """Boxes on one image and no mask slot: a dataset imported with boxes only."""
    target = Path(tempfile.mkdtemp()) / DATASET_ID
    created = Dataset.create(
        target,
        DatasetInfo(id=DATASET_ID, name=DATASET_ID, record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )
    created.add_records(
        {
            "records": Record(id="r1"),
            "images": Image(
                id="img1", record_id="r1", logical_name="image", uri="a.png", width=IMAGE_WIDTH, height=IMAGE_HEIGHT
            ),
        },
        check_integrity="none",
    )
    created.add_data("entities", [Entity(id="e1", record_id="r1")], raise_or_warn="none")
    created.add_data(
        "bboxes",
        [
            BBox(
                id="b1",
                record_id="r1",
                entity_id="e1",
                view_id="img1",
                coords=[0.1, 0.1, 0.5, 0.5],
                format="xyxy",
                is_normalized=True,
            )
        ],
        raise_or_warn="none",
    )
    return created


@pytest.fixture
def client(dataset: Dataset) -> TestClient:
    models_dir = Path(tempfile.mkdtemp()) / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(dataset.path.parent), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app)


def _model_mask() -> CompressedRLE:
    """A mask the way a job writes it: on the box's entity, from a model, pending review."""
    return CompressedRLE.from_mask(
        np.ones((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.uint8),
        id="m1",
        record_id="r1",
        entity_id="e1",
        view_id="img1",
        source_type="model",
        source_name="segmentation",
        review_status="pending",
    )


def _as_the_worker(worker: Dataset) -> None:
    """What the worker does, in its own process: no invalidation hook reaches the API."""
    hooks = Dataset._cache_invalidation_hooks
    Dataset._cache_invalidation_hooks = []
    try:
        assert worker.ensure_annotation_table(MASK_SLOT) == MASK_TABLE
        worker.add_data(MASK_TABLE, [_model_mask()], raise_or_warn="none")
    finally:
        Dataset._cache_invalidation_hooks = hooks


def _info_json_identity(dataset: Dataset) -> tuple[int, int, str]:
    """What a rewrite changes: a rename gives `info.json` a new inode."""
    file_stat = dataset._info_file.stat()
    return file_stat.st_ino, file_stat.st_mtime_ns, dataset._info_file.read_text(encoding="utf-8")


class TestMaskTableAddedElsewhere:
    def test_the_worker_s_masks_are_served(
        self, dataset: Dataset, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        assert client.get(f"{BASE}/bboxes").status_code == 200  # the API now holds the dataset

        _as_the_worker(Dataset(dataset.path))
        after_the_job = _info_json_identity(dataset)
        with caplog.at_level(logging.WARNING):
            resp = client.get(f"{BASE}/masks")

        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert [(item["id"], item["entity_id"], item["size"]) for item in items] == [
            ("m1", "e1", [IMAGE_HEIGHT, IMAGE_WIDTH])
        ]
        assert API_CREATION_LOG not in caplog.text
        assert _info_json_identity(dataset) == after_the_job

    def test_the_worker_s_mask_can_be_reviewed(self, dataset: Dataset, client: TestClient) -> None:
        assert client.get(f"{BASE}/bboxes").status_code == 200

        _as_the_worker(Dataset(dataset.path))
        resp = client.put(f"{BASE}/masks/m1", json={"review_status": "accepted"})

        assert resp.status_code == 200, resp.text
        assert Dataset(dataset.path).get_data(MASK_TABLE, ids=["m1"])[0].review_status == "accepted"

    def test_a_table_the_api_created_first_is_not_created_again(
        self, dataset: Dataset, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A record opened before the job wrote: the API creates the table, the worker's dataset
        predates it."""
        worker = Dataset(dataset.path)
        with caplog.at_level(logging.WARNING):
            assert client.get(f"{BASE}/masks").json()["items"] == []
        assert API_CREATION_LOG in caplog.text  # the premise: the API made the table
        after_the_api = _info_json_identity(dataset)

        _as_the_worker(worker)

        assert _info_json_identity(dataset) == after_the_api
        masks = Dataset(dataset.path).get_data(MASK_TABLE)
        assert [(mask.id, mask.entity_id) for mask in masks] == [("m1", "e1")]
