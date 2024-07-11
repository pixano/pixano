# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path

from pixano.datasets.dataset_stat import DatasetStat


class TestDatasetStat:
    def test_init(self):
        stat = DatasetStat(name="stat", type="numerical", histogram=[{"key": 2, "value": 3}], range=[1, 2])
        assert set(stat.model_fields.keys()) == {"name", "type", "histogram", "range"}

    def test_to_json(self):
        stat = DatasetStat(name="stat", type="numerical", histogram=[{"key": 2, "value": 3}], range=[1, 2])

        json_fp = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        stat.to_json(json_fp)
        assert (
            json_fp.read_text()
            == """[
    {
        "name": "stat",
        "type": "numerical",
        "histogram": [
            {
                "key": 2,
                "value": 3
            }
        ],
        "range": [
            1,
            2
        ]
    }
]"""
        )

        stat_replace = DatasetStat(name="stat", type="numerical", histogram=[{"yolo": 4, "value": 5}])
        stat_not_replace = DatasetStat(name="stat2", type="numerical", histogram=[{"key": 2, "value": 3}])

        stat_replace.to_json(json_fp)
        stat_not_replace.to_json(json_fp)
        assert (
            json_fp.read_text()
            == """[
    {
        "name": "stat",
        "type": "numerical",
        "histogram": [
            {
                "yolo": 4,
                "value": 5
            }
        ],
        "range": null
    },
    {
        "name": "stat2",
        "type": "numerical",
        "histogram": [
            {
                "key": 2,
                "value": 3
            }
        ],
        "range": null
    }
]"""
        )
