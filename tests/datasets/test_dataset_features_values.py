# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import tempfile
from pathlib import Path

from pixano.datasets.dataset_features_values import DatasetFeaturesValues


class TestDatasetFeaturesValues:
    def test_init(self):
        fv = DatasetFeaturesValues()
        assert DatasetFeaturesValues(items={}, views={}, entities={}, annotations={}) == fv

        fv = DatasetFeaturesValues(
            items={"item1": ["value1", "value2"]},
            views={"view1": ["value1", "value2"]},
            entities={"entity1": ["value1", "value2"]},
            annotations={"annotation1": ["value1", "value2"]},
        )
        assert set(fv.model_fields.keys()) == {"items", "views", "entities", "annotations"}

    def test_to_json(self):
        fv = DatasetFeaturesValues(
            items={"item1": ["value1", "value2"]},
            views={"view1": ["value1", "value2"]},
            entities={"entity1": ["value1", "value2"]},
            annotations={"annotation1": ["value1", "value2"]},
        )
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        fv.to_json(temp_file)
        assert (
            Path(temp_file).read_text()
            == """{
    "items": {
        "item1": [
            "value1",
            "value2"
        ]
    },
    "views": {
        "view1": [
            "value1",
            "value2"
        ]
    },
    "entities": {
        "entity1": [
            "value1",
            "value2"
        ]
    },
    "annotations": {
        "annotation1": [
            "value1",
            "value2"
        ]
    }
}"""
        )

    def test_from_json(self):
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        temp_file.write_text(
            """{
    "items": {
        "item1": [
            "value1",
            "value2"
        ]
    },
    "views": {
        "view1": [
            "value1",
            "value2"
        ]
    },
    "entities": {
        "entity1": [
            "value1",
            "value2"
        ]
    },
    "annotations": {
        "annotation1": [
            "value1",
            "value2"
        ]
    }
}"""
        )
        fv = DatasetFeaturesValues.from_json(temp_file)
        assert (
            DatasetFeaturesValues(
                items={"item1": ["value1", "value2"]},
                views={"view1": ["value1", "value2"]},
                entities={"entity1": ["value1", "value2"]},
                annotations={"annotation1": ["value1", "value2"]},
            )
            == fv
        )
