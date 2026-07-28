# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path

import pytest

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import (
    Classification,
    Entity,
    Image,
    Record,
    Relation,
    canonical_table_name_for_schema,
    supported_dataset_info_slots,
)


class TestNewCanonicalFamilies:
    @pytest.mark.parametrize(
        "schema_cls,table_name",
        [
            (Classification, "classifications"),
            (Relation, "relations"),
        ],
    )
    def test_canonical_table_name(self, schema_cls, table_name):
        assert canonical_table_name_for_schema(schema_cls) == table_name

    def test_new_slots_supported(self):
        slots = supported_dataset_info_slots()
        assert "classification" in slots
        assert "relation" in slots
        # Upstream defers 3D families to 0.9; this branch already ships bbox3d.
        assert "bbox3d" in slots
        assert "keypoints3d" not in slots
        assert "cam_calibration" not in slots


class TestNewSlotsDatasetInfoRoundTrip:
    def test_info_json_round_trip(self):
        info = DatasetInfo(
            name="classified",
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            classification=Classification,
            relation=Relation,
            views={"image": Image},
        )
        assert info.tables["classifications"] is Classification
        assert info.tables["relations"] is Relation

        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        info.to_json(temp_file)
        loaded = DatasetInfo.from_json(temp_file)

        assert set(loaded.tables) == set(info.tables)
        assert loaded.classification is Classification
        assert loaded.relation is Relation
