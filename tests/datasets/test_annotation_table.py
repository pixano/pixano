# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A job gives a dataset the annotation table it writes into.

A dataset built with boxes and keypoints only gets no mask table: a job that writes masks adds its `masks` table
the way `ensure_entity_text_field` adds a class field to the entities, without re-serializing `info.json`.
"""

import json
import stat
import tempfile
from pathlib import Path
from typing import Any

import lancedb
import numpy as np
import pytest
from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record


MASK_SLOT = "mask"
MASK_TABLE = "masks"
# Non-square, so that a swapped height and width shows.
IMAGE_HEIGHT = 48
IMAGE_WIDTH = 64
# A view whose schema comes from a later build: `DatasetInfo.from_json` drops it, the file keeps it.
UNREADABLE_VIEW_NAME = "lidar"
UNREADABLE_VIEW = {"base": "FutureView", "fields": {}}
# Readable by the owner and everyone else: what a dataset copied in by hand usually carries.
SHARED_PERMISSIONS = 0o644


def _dataset() -> Dataset:
    """A dataset of boxes on one image, with no mask slot: a dataset imported with boxes only."""
    target = Path(tempfile.mkdtemp()) / "ds"
    dataset = Dataset.create(
        target, DatasetInfo(name="ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image})
    )
    dataset.add_records(
        {
            "records": Record(id="r1"),
            "images": Image(
                id="img1", record_id="r1", logical_name="image", uri="a.png", width=IMAGE_WIDTH, height=IMAGE_HEIGHT
            ),
        },
        check_integrity="none",
    )
    dataset.add_data("entities", [Entity(id="e1", record_id="r1")], raise_or_warn="none")
    return dataset


def _mask(mask_id: str = "m1") -> CompressedRLE:
    return CompressedRLE.from_mask(
        np.ones((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.uint8),
        id=mask_id,
        record_id="r1",
        entity_id="e1",
        view_id="img1",
    )


def _info_json(dataset: Dataset) -> dict[str, Any]:
    return json.loads(dataset._info_file.read_text(encoding="utf-8"))


def _write_info_json(dataset: Dataset, info_json: dict[str, Any]) -> None:
    dataset._info_file.write_text(json.dumps(info_json, indent=4), encoding="utf-8")


def _with_unreadable_view(dataset: Dataset) -> Dataset:
    """The dataset reopened after a later build gave it a view this one cannot read."""
    info_json = _info_json(dataset)
    info_json["views"][UNREADABLE_VIEW_NAME] = UNREADABLE_VIEW
    _write_info_json(dataset, info_json)
    reopened = Dataset(dataset.path)
    assert UNREADABLE_VIEW_NAME not in reopened.info.views  # dropped on read, the premise
    return reopened


def _file_identity(dataset: Dataset) -> tuple[int, int, str]:
    """What a rewrite changes: a rename gives `info.json` a new inode."""
    file_stat = dataset._info_file.stat()
    return file_stat.st_ino, file_stat.st_mtime_ns, dataset._info_file.read_text(encoding="utf-8")


def _leftover_temporary_files(dataset: Dataset) -> list[Path]:
    return list(dataset.path.glob(f"{Dataset._INFO_FILE}.*.tmp"))


class TestEnsureAnnotationTable:
    def test_creates_the_table_and_declares_the_slot(self) -> None:
        dataset = _dataset()

        assert dataset.ensure_annotation_table(MASK_SLOT) == MASK_TABLE

        assert dataset.info.mask is CompressedRLE
        assert dataset.info.tables[MASK_TABLE] is CompressedRLE
        assert dataset.open_table(MASK_TABLE).count_rows() == 0
        assert (dataset.path / Dataset._DB_PATH / f"{MASK_TABLE}.lance").is_dir()
        assert _info_json(dataset)[MASK_SLOT] == {"base": "CompressedRLE", "fields": {}}
        assert _leftover_temporary_files(dataset) == []

    def test_the_slot_survives_a_reopen(self) -> None:
        dataset = _dataset()
        dataset.ensure_annotation_table(MASK_SLOT)

        reopened = Dataset(dataset.path)

        assert reopened.info.mask is CompressedRLE
        assert MASK_TABLE in reopened.info.tables

    def test_a_mask_can_be_written_afterwards(self) -> None:
        dataset = _dataset()
        dataset.ensure_annotation_table(MASK_SLOT)

        dataset.add_data(MASK_TABLE, [_mask()], raise_or_warn="none")

        masks = Dataset(dataset.path).get_data(MASK_TABLE)
        assert [(mask.id, mask.entity_id, mask.size) for mask in masks] == [("m1", "e1", [IMAGE_HEIGHT, IMAGE_WIDTH])]

    def test_is_idempotent_and_does_not_rewrite_info_json(self) -> None:
        """A worker calls it at every write: the API must not reopen the dataset each time."""
        dataset = _dataset()
        dataset.ensure_annotation_table(MASK_SLOT)
        dataset.add_data(MASK_TABLE, [_mask()], raise_or_warn="none")
        before = _file_identity(dataset)

        assert dataset.ensure_annotation_table(MASK_SLOT) == MASK_TABLE

        assert _file_identity(dataset) == before
        assert [mask.id for mask in Dataset(dataset.path).get_data(MASK_TABLE)] == ["m1"]

    def test_leaves_a_slot_declared_with_its_own_schema_as_it_is(self) -> None:
        """VOC declares its masks with a schema of its own."""
        voc_mask = create_model("VocMask", __base__=CompressedRLE, difficult=(bool, False))
        target = Path(tempfile.mkdtemp()) / "voc"
        dataset = Dataset.create(
            target, DatasetInfo(name="voc", record=Record, entity=Entity, mask=voc_mask, views={"image": Image})
        )
        before = _file_identity(dataset)

        assert dataset.ensure_annotation_table(MASK_SLOT) == MASK_TABLE

        assert _file_identity(dataset) == before
        assert Dataset(dataset.path).info.mask.__name__ == "VocMask"

    def test_keeps_views_this_build_cannot_deserialize(self) -> None:
        dataset = _with_unreadable_view(_dataset())

        dataset.ensure_annotation_table(MASK_SLOT)

        info_json = _info_json(dataset)
        assert info_json["views"][UNREADABLE_VIEW_NAME] == UNREADABLE_VIEW
        assert info_json[MASK_SLOT] == {"base": "CompressedRLE", "fields": {}}

    def test_keeps_the_permissions_of_info_json(self) -> None:
        """A temporary file is created readable by its owner alone; the rename must not carry that over."""
        dataset = _dataset()
        dataset._info_file.chmod(SHARED_PERMISSIONS)

        dataset.ensure_annotation_table(MASK_SLOT)

        assert stat.S_IMODE(dataset._info_file.stat().st_mode) == SHARED_PERMISSIONS

    @pytest.mark.parametrize("slot", ["record", "entity", "entity_dynamic_state", "image", "embedding", "timeseries"])
    def test_refuses_a_slot_that_holds_no_annotations(self, slot: str) -> None:
        dataset = _dataset()
        before = _file_identity(dataset)

        with pytest.raises(ValueError, match="holds no annotations"):
            dataset.ensure_annotation_table(slot)

        assert _file_identity(dataset) == before

    def test_refuses_a_slot_that_does_not_exist(self) -> None:
        with pytest.raises(ValueError, match="Unsupported DatasetInfo slot"):
            _dataset().ensure_annotation_table("masks")

    def test_opens_a_table_created_but_never_declared(self) -> None:
        """What a crash between the creation and the declaration leaves behind."""
        dataset = _dataset()
        lancedb.connect(dataset.path / Dataset._DB_PATH).create_table(MASK_TABLE, schema=CompressedRLE)

        assert dataset.ensure_annotation_table(MASK_SLOT) == MASK_TABLE

        dataset.add_data(MASK_TABLE, [_mask()], raise_or_warn="none")
        assert [mask.id for mask in Dataset(dataset.path).get_data(MASK_TABLE)] == ["m1"]


class TestAnotherInstance:
    """The worker and the API each hold their own `Dataset`, in their own process."""

    def test_a_stale_instance_finds_the_table_another_created(self) -> None:
        held = _dataset()
        Dataset(held.path).ensure_annotation_table(MASK_SLOT)
        after_creation = _file_identity(held)

        assert held.ensure_annotation_table(MASK_SLOT) == MASK_TABLE

        assert _file_identity(held) == after_creation
        held.add_data(MASK_TABLE, [_mask()], raise_or_warn="none")
        assert [mask.id for mask in Dataset(held.path).get_data(MASK_TABLE)] == ["m1"]

    def test_a_stale_instance_finds_the_table_the_api_created(self) -> None:
        """The API creates a missing annotation table when a record is opened: `create_table`, then
        the slot set and `info.json` re-serialized, as `BaseService.resolve_table` does."""
        held = _dataset()
        api = Dataset(held.path)
        api.create_table(MASK_TABLE, CompressedRLE, exist_ok=True)
        api.info.mask = CompressedRLE
        api.info.to_json(api._info_file)
        after_creation = _file_identity(held)

        assert held.ensure_annotation_table(MASK_SLOT) == MASK_TABLE

        assert _file_identity(held) == after_creation

    def test_the_creation_makes_another_holder_stale(self) -> None:
        """How the API's cache learns of the new table."""
        held = _dataset()

        Dataset(held.path).ensure_annotation_table(MASK_SLOT)

        assert held.is_stale()

    def test_its_own_creation_does_not_make_it_stale(self) -> None:
        dataset = _dataset()

        dataset.ensure_annotation_table(MASK_SLOT)

        assert not dataset.is_stale()

    def test_a_call_that_finds_the_table_does_not_make_another_holder_stale(self) -> None:
        dataset = _dataset()
        dataset.ensure_annotation_table(MASK_SLOT)
        held = Dataset(dataset.path)

        dataset.ensure_annotation_table(MASK_SLOT)

        assert not held.is_stale()
