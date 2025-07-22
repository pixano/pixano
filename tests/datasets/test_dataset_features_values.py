# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import tempfile
from pathlib import Path

from pixano.datasets.dataset_features_values import Constraint, ConstraintDict, DatasetFeaturesValues, TableName


class TestDatasetFeaturesValues:
    def test_init(self):
        fv = DatasetFeaturesValues()
        assert DatasetFeaturesValues(item={}, views={}, entities={}, annotations={}) == fv

        fv = DatasetFeaturesValues(
            item={"item1": [Constraint("field_i1", True, ["value1", "value2"])]},
            views={},
            entities={
                "entity1": [
                    Constraint("field_e1", True, ["value1", "value2"]),
                    Constraint("field_e2", False, ["value1", "value2"]),
                ]
            },
            annotations={"annotation1": []},
        )
        assert set(fv.model_fields.keys()) == {"item", "views", "entities", "annotations"}

    def test_to_json(self):
        fv = DatasetFeaturesValues(
            item={"item1": [Constraint("field_i1", True, ["value1", "value2"])]},
            views={},
            entities={
                "entity1": [
                    Constraint("field_e1", True, ["value1", "value2"]),
                    Constraint("field_e2", False, ["value1", "value2"]),
                ]
            },
            annotations={"annotation1": []},
        )
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        fv.to_json(temp_file)
        assert (
            Path(temp_file).read_text()
            == """{
    "item": {
        "item1": [
            {
                "name": "field_i1",
                "restricted": true,
                "values": [
                    "value1",
                    "value2"
                ]
            }
        ]
    },
    "views": {},
    "entities": {
        "entity1": [
            {
                "name": "field_e1",
                "restricted": true,
                "values": [
                    "value1",
                    "value2"
                ]
            },
            {
                "name": "field_e2",
                "restricted": false,
                "values": [
                    "value1",
                    "value2"
                ]
            }
        ]
    },
    "annotations": {
        "annotation1": []
    }
}"""
        )

    def test_from_json(self):
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        temp_file.write_text(
            """{
    "item": {
        "item1": [
            {
                "name": "field_i1",
                "restricted": true,
                "values": [
                    "value1",
                    "value2"
                ]
            }
        ]
    },
    "views": {},
    "entities": {
        "entity1": [
            {
                "name": "field_e1",
                "restricted": true,
                "values": [
                    "value1",
                    "value2"
                ]
            },
            {
                "name": "field_e2",
                "restricted": false,
                "values": [
                    "value1",
                    "value2"
                ]
            }
        ]
    },
    "annotations": {
        "annotation1": []
    }
}"""
        )
        fv = DatasetFeaturesValues.from_json(temp_file)
        assert (
            DatasetFeaturesValues(
                item={"item1": [Constraint("field_i1", True, ["value1", "value2"])]},
                views={},
                entities={
                    "entity1": [
                        Constraint("field_e1", True, ["value1", "value2"]),
                        Constraint("field_e2", False, ["value1", "value2"]),
                    ]
                },
                annotations={"annotation1": []},
            )
            == fv
        )
