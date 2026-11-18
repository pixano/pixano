# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a kind reads through the reader beside its media: an image's size, and the rows a filter
selects — on a real dataset, through the reader the runner gives a job."""

import io
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pytest
from PIL import Image as PILImage
from pixano_worker import runner
from pixano_worker.media import MediaResolver
from pixano_worker.reader import JobReader

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record


DATASET_ID = "sizes"
IMAGES_TABLE = "images"
BBOX_TABLE = "bboxes"
# Wider than tall, so that width and height given the wrong way round show.
WIDTH, HEIGHT = 200, 100
# The file a view names that is not on the worker's storage.
ABSENT_FILE = "absent.png"


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (width, height)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    """The worker's media storage: one image, and a file that is not one."""
    root = tmp_path / "media"
    root.mkdir()
    (root / "on_disk.png").write_bytes(_png(WIDTH, HEIGHT))
    (root / "not_an_image.png").write_bytes(b"not an image")
    return root


@pytest.fixture
def reader(tmp_path: Path, media_root: Path, monkeypatch: pytest.MonkeyPatch) -> JobReader:
    """The reader the runner gives a job, on a dataset whose images are each found another way."""
    # The runner caches the datasets it opened, module-wide: an empty cache keeps tests apart.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name="Sizes", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )
    views: dict[str, dict[str, Any]] = {
        # The dataset records the size; the file is nowhere.
        "recorded": {"uri": ABSENT_FILE, "width": WIDTH, "height": HEIGHT},
        # Imported by reference, without a size: the file is on the worker's storage.
        "on_disk": {"uri": str(media_root / "on_disk.png")},
        # Embedded in the dataset, without a size.
        "embedded": {"raw_bytes": _png(WIDTH, HEIGHT)},
        "not_an_image": {"uri": str(media_root / "not_an_image.png")},
        "absent": {"uri": ABSENT_FILE},
    }
    dataset.add_records({"records": [Record(id=f"r-{view_id}") for view_id in views]})
    dataset.add_data(
        IMAGES_TABLE,
        [
            Image(**{"width": 0, "height": 0, **fields}, id=view_id, record_id=f"r-{view_id}", logical_name="image")
            for view_id, fields in views.items()
        ],
        raise_or_warn="none",
    )
    return runner._reader_for(library, DATASET_ID, MediaResolver(str(media_root), "/inference-media"), fresh=True)


def _size(reader: JobReader, view_id: str) -> tuple[int, int] | None:
    (view,) = reader.rows(IMAGES_TABLE, [view_id])
    return reader.image_size(IMAGES_TABLE, view)


class TestImageSize:
    def test_the_recorded_size_needs_no_file(self, reader: JobReader) -> None:
        assert _size(reader, "recorded") == (WIDTH, HEIGHT)

    def test_without_a_recorded_size_it_is_read_from_the_file(self, reader: JobReader) -> None:
        """A dataset imported by reference records no size, and its views carry no bytes."""
        assert _size(reader, "on_disk") == (WIDTH, HEIGHT)

    def test_without_a_recorded_size_it_is_read_from_the_embedded_bytes(self, reader: JobReader) -> None:
        assert _size(reader, "embedded") == (WIDTH, HEIGHT)

    @pytest.mark.parametrize("view_id", ["not_an_image", "absent"])
    def test_an_image_the_worker_cannot_read_has_no_size(self, reader: JobReader, view_id: str) -> None:
        assert _size(reader, view_id) is None

    @pytest.mark.parametrize("view_id", ["on_disk", "embedded"])
    def test_an_image_too_large_for_pillows_guard_has_no_size(
        self, reader: JobReader, view_id: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pillow refuses an image beyond twice its pixel limit with an error that is not an
        OSError: escaping, it would fail a whole chunk for one image."""
        monkeypatch.setattr(PILImage, "MAX_IMAGE_PIXELS", WIDTH * HEIGHT // 4)

        assert _size(reader, view_id) is None


class TestRead:
    @pytest.fixture
    def boxes(self, reader: JobReader) -> JobReader:
        """Two boxes on one view, one on another; one of the first two drawn by a model."""
        reader.dataset.add_data(  # type: ignore[attr-defined]
            BBOX_TABLE,
            [
                BBox(
                    id=box_id,
                    record_id=f"r-{view_id}",
                    view_id=view_id,
                    coords=[0.1, 0.1, 0.2, 0.2],
                    format="xywh",
                    is_normalized=True,
                    **fields,
                )
                for box_id, view_id, fields in [
                    ("b1", "on_disk", {"source_type": "human"}),
                    ("b2", "on_disk", {"source_type": "model", "review_status": "pending"}),
                    ("b3", "embedded", {"source_type": "human"}),
                ]
            ],
        )
        return reader

    def test_reads_the_rows_a_filter_selects(self, boxes: JobReader) -> None:
        assert sorted(row.id for row in boxes.read(BBOX_TABLE, "view_id IN ('on_disk')")) == ["b1", "b2"]

    def test_a_filter_may_combine_conditions(self, boxes: JobReader) -> None:
        rows = boxes.read(BBOX_TABLE, "view_id IN ('on_disk', 'embedded') AND source_type = 'human'")

        assert sorted(row.id for row in rows) == ["b1", "b3"]

    def test_a_filter_that_selects_nothing_reads_nothing(self, boxes: JobReader) -> None:
        assert boxes.read(BBOX_TABLE, "view_id IN ('absent')") == []

    def test_rows_come_back_typed_by_the_table(self, boxes: JobReader) -> None:
        """A kind reads a box's fields, not a dictionary."""
        (row,) = boxes.read(BBOX_TABLE, "id IN ('b1')")

        assert isinstance(row, BBox)
        assert row.coords == [0.1, 0.1, 0.2, 0.2]
