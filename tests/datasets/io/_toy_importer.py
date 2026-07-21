# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A minimal deterministic importer used by the engine tests and the kill-9 helper."""

from typing import Iterator

from pixano.datasets.io import AnalyzeLimits, BatchBundle, DatasetImporter, ImportPlan, stable_id
from pixano.schemas import Entity, Image, Record


class ToyImporter(DatasetImporter):
    """Emits `num_records` records with one image view and one entity each, in bundles of `batch_size`."""

    format_name = "toy"
    importer_version = "1.0.0"
    supports_resume = True
    deterministic_ids = True

    def __init__(
        self,
        num_records: int = 10,
        batch_size: int = 4,
        media: str = "embed",
        image_bytes: bytes = b"\x89PNG-fake",
        duplicate_record_ordinal: int | None = None,
    ):
        self.num_records = num_records
        self.batch_size = batch_size
        self.media = media
        self.image_bytes = image_bytes
        self.duplicate_record_ordinal = duplicate_record_ordinal

    def analyze(self, source, spec, limits: AnalyzeLimits) -> ImportPlan:
        plan = ImportPlan(format=self.format_name, importer_version=self.importer_version)
        plan.totals.records = self.num_records
        return plan

    def iter_batches(self, source, spec, plan, cursor=None) -> Iterator[BatchBundle]:
        namespace = spec.ids.namespace or "toy"
        start = int(cursor["ordinal"]) if cursor else 0
        for begin in range(start, self.num_records, self.batch_size):
            tables: dict = {"records": [], "images": [], "entities": []}
            for ordinal in range(begin, min(begin + self.batch_size, self.num_records)):
                effective = (
                    self.duplicate_record_ordinal
                    if self.duplicate_record_ordinal is not None and ordinal == self.num_records - 1
                    else ordinal
                )
                record_id = stable_id(namespace, "record", effective)
                tables["records"].append(Record(id=record_id, split="train"))
                media_kwargs = (
                    {"raw_bytes": self.image_bytes}
                    if self.media == "embed"
                    else {"uri": f"https://example.com/{ordinal}.png"}
                )
                tables["images"].append(
                    Image(
                        id=stable_id(namespace, "image", effective),
                        record_id=record_id,
                        logical_name="image",
                        width=4,
                        height=4,
                        format="PNG",
                        **media_kwargs,
                    )
                )
                tables["entities"].append(Entity(id=stable_id(namespace, "entity", effective), record_id=record_id))
            yield BatchBundle(tables=tables, cursor={"ordinal": min(begin + self.batch_size, self.num_records)})
