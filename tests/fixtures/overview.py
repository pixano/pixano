# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset whose overview is known: records in three splits, images of known sizes, objects of known classes.

Its objects have a box each, and its default statistics are written as the statistics job would.
"""

from datetime import datetime, timezone
from pathlib import Path

from pydantic import create_model

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.statistic_choices import default_statistics
from pixano.schemas import BBox, Entity, Image, Record
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import StatisticLevel


OVERVIEW_DATASET_ID = "overview_ds"

WeatherRecord = create_model("WeatherRecord", __base__=Record, weather=(str, ""), rank=(int, 0), sunny=(bool, False))
ClassedEntity = create_model("ClassedEntity", __base__=Entity, category=(str, ""))

# Four records: two in train, one in val, one in test without any image or object.
RECORDS = [
    WeatherRecord(id="r1", split="train", weather="rain", rank=1, sunny=False),
    WeatherRecord(id="r2", split="train", weather="sun", rank=2, sunny=True),
    WeatherRecord(id="r3", split="val", weather="rain", rank=3, sunny=False),
    WeatherRecord(id="r4", split="test", weather="", rank=4, sunny=False),
]
IMAGES = [
    Image(id="i1", record_id="r1", logical_name="image", url="1.jpg", width=640, height=480, format="JPEG"),
    Image(id="i2", record_id="r2", logical_name="image", url="2.png", width=640, height=480, format="png"),
    Image(id="i3", record_id="r3", logical_name="image", url="3.jpg", width=320, height=320, format="jpeg"),
]
OBJECTS = [
    ClassedEntity(id="e1", record_id="r1", category="dog"),
    ClassedEntity(id="e2", record_id="r1", category="cat"),
    ClassedEntity(id="e3", record_id="r2", category="dog"),
    ClassedEntity(id="e4", record_id="r3", category="bird"),
]
OBJECTS_PER_RECORD = {"r1": 2, "r2": 1, "r3": 1, "r4": 0}
BOX_SHARES = {"e1": 0.1, "e2": 0.2, "e3": 0.5, "e4": 0.05}
RECORD_OF = {entity.id: entity.record_id for entity in OBJECTS}
COMPUTED_AT = datetime(2026, 11, 10, tzinfo=timezone.utc)
BOXES = [
    BBox(
        id=f"b{entity.id}",
        record_id=entity.record_id,
        entity_id=entity.id,
        coords=[0, 0, 0.5, 0.5],
        format="xywh",
        is_normalized=True,
    )
    for entity in OBJECTS
]


def build_overview_dataset(library: Path) -> Dataset:
    """The dataset once imported into a library, its default statistics computed."""
    info = DatasetInfo(
        id=OVERVIEW_DATASET_ID,
        name=OVERVIEW_DATASET_ID,
        record=WeatherRecord,
        entity=ClassedEntity,
        bbox=BBox,
        views={"image": Image},
    )
    dataset = Dataset.create(library / OVERVIEW_DATASET_ID, info)
    dataset.add_records({"records": RECORDS, "images": IMAGES})
    dataset.add_data("entities", OBJECTS, raise_or_warn="none")
    dataset.add_data("bboxes", BOXES, raise_or_warn="none")
    by_name = {statistic.name: statistic for statistic in default_statistics(dataset)}
    objects, boxes, share = by_name["entity_count"], by_name["bbox_count"], by_name["bbox_to_image_ratio_mean"]
    record_columns = {objects.name: "int", boxes.name: "int"}
    dataset.ensure_statistic_columns(StatisticLevel.RECORD, record_columns)
    dataset.write_statistic_values(
        StatisticLevel.RECORD,
        [
            {"record_id": record, objects.name: count, boxes.name: count}
            for record, count in OBJECTS_PER_RECORD.items()
        ],
        record_columns,
    )
    dataset.ensure_statistic_columns(StatisticLevel.ENTITY, {share.name: "float"})
    dataset.write_statistic_values(
        StatisticLevel.ENTITY,
        [
            {"record_id": RECORD_OF[entity], "entity_id": entity, share.name: value}
            for entity, value in BOX_SHARES.items()
        ],
        {share.name: "float"},
    )
    computed_at = COMPUTED_AT
    dataset.record_computed_statistics(
        [
            ComputedStatistic(definition=statistic, job_id="job-1", computed_at=computed_at)
            for statistic in by_name.values()
        ]
    )
    return dataset
