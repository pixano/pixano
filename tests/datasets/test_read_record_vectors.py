# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Every vector of one model's embeddings, read at once for a computation over the whole dataset."""

from pathlib import Path

import pytest

from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.features import Image, Record


#: More records than LanceDB returns by default from a search without a limit: ten.
RECORDS = 12
#: The dimensions of the two models' vectors.
CLIP_DIM, SIGLIP_DIM = 4, 3


def _image(record_id: str) -> Image:
    return Image(id=f"img-{record_id}", record_id=record_id, logical_name="image", uri=f"{record_id}.jpg")


@pytest.fixture
def dataset(tmp_path: Path) -> Dataset:
    """Records whose images two models embedded: clip, the default, then siglip, with other vectors."""
    dataset = Dataset.create(tmp_path / "ds", DatasetInfo(name="ds", record=Record, views={"image": Image}))
    record_ids = [f"r{n:02d}" for n in range(RECORDS)]
    dataset.add_records({"records": [Record(id=record_id) for record_id in record_ids]})
    dataset.add_data("images", [_image(record_id) for record_id in record_ids], raise_or_warn="none")
    for model, checkpoint, dim, value in (("clip", "a", CLIP_DIM, 1.0), ("siglip", "b", SIGLIP_DIM, 2.0)):
        space = dataset.ensure_record_embedding_space(model, checkpoint, dim=dim)
        rows = [{"record_id": rid, "view_id": f"img-{rid}", "vector": [value] * dim} for rid in record_ids]
        dataset.add_record_embeddings(rows, space["id"])
    return dataset


class TestReadRecordVectors:
    def test_the_default_models_every_vector_with_its_record_and_medium(self, dataset: Dataset) -> None:
        table = dataset.read_record_vectors()

        assert table is not None
        assert table.column_names == ["record_id", "view_id", "vector"]
        assert table.num_rows == RECORDS
        assert {len(vector) for vector in table.column("vector").to_pylist()} == {CLIP_DIM}
        assert set(table.column("view_id").to_pylist()) == {f"img-r{n:02d}" for n in range(RECORDS)}

    def test_a_model_named_by_its_name_or_its_spaces_id(self, dataset: Dataset) -> None:
        siglip = next(space for space in dataset.record_embedding_spaces() if space["model_id"] == "siglip")

        by_name = dataset.read_record_vectors("siglip")
        by_id = dataset.read_record_vectors(siglip["id"])

        assert by_name is not None and by_id is not None
        assert {tuple(vector) for vector in by_name.column("vector").to_pylist()} == {(2.0,) * SIGLIP_DIM}
        assert by_id.num_rows == by_name.num_rows == RECORDS

    def test_none_for_a_model_the_dataset_holds_no_embeddings_of(self, dataset: Dataset) -> None:
        assert dataset.read_record_vectors("dinov2") is None

    def test_none_without_embeddings(self, tmp_path: Path) -> None:
        empty = Dataset.create(tmp_path / "empty", DatasetInfo(name="empty", record=Record, views={"image": Image}))

        assert empty.read_record_vectors() is None

    def test_none_once_another_writer_dropped_the_models_table(self, dataset: Dataset) -> None:
        """This instance still knows the space; its table is gone."""
        clip = dataset.record_embedding_space("clip")
        assert clip is not None
        Dataset(dataset.path)._db_connection.drop_table(clip["table"])

        assert dataset.read_record_vectors("clip") is None
