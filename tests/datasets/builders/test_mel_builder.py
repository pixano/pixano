# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

from pixano.datasets import DatasetInfo
from pixano.datasets.builders.folders import MelFolderBuilder
from pixano.schemas import Image, Text, TextSpan, canonical_table_name_for_schema, canonical_table_name_for_slot
from tests.assets.sample_data.metadata import SAMPLE_DATA_PATHS


def _create_mel_source(root: Path) -> Path:
    source_dir = root / "mel_sample"
    split_dir = source_dir / "train"
    split_dir.mkdir(parents=True, exist_ok=True)

    image_path = split_dir / "sample.png"
    image_path.write_bytes(SAMPLE_DATA_PATHS["image_png"].read_bytes())

    text_path = split_dir / "sample.txt"
    text_path.write_text("FactoryIA builds vision tools.", encoding="utf-8")

    metadata = {
        "views": {
            "image": "sample.png",
            "text": "sample.txt",
        },
        "entities": [
            {
                "name": "Logo",
                "annotations": {
                    "image": {"bbox": [0.1, 0.2, 0.3, 0.4]},
                    "text": {
                        "text_span": {
                            "mention": "FactoryIA",
                            "spans_start": [0],
                            "spans_end": [9],
                        }
                    },
                },
            }
        ],
    }
    (split_dir / "metadata.jsonl").write_text(json.dumps(metadata) + "\n", encoding="utf-8")
    return source_dir


def test_mel_builder_generates_image_text_and_text_spans(tmp_path: Path):
    source_dir = _create_mel_source(tmp_path)
    builder = MelFolderBuilder(
        source_dir=source_dir,
        library_dir=tmp_path / "library",
        info=DatasetInfo(name="mel", description="mel sample"),
    )

    batches = list(builder.generate_data())

    assert len(batches) == 4
    assert builder.views_schema == {"image": Image, "text": Text}
    assert builder.annotations_schema[canonical_table_name_for_slot("text_span")] is TextSpan

    record_batch = batches[0]
    image_batch = batches[1]
    text_batch = batches[2]
    component_batch = batches[3]

    record = record_batch[builder.record_table_name]
    image = image_batch[canonical_table_name_for_schema(Image)]
    text = text_batch[canonical_table_name_for_schema(Text)]
    text_spans = component_batch[canonical_table_name_for_slot("text_span")]

    assert record.split == "train"
    assert image.logical_name == "image"
    assert text.logical_name == "text"
    assert text.content == "FactoryIA builds vision tools."
    assert len(text_spans) == 1
    assert text_spans[0].mention == "FactoryIA"
    assert text_spans[0].entity_id != ""
    assert text_spans[0].view_id == text.id
