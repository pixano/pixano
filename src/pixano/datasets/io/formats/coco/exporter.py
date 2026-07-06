# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""COCO exporter: streams a dataset back to instances_<split>.json (spec §10).

Reader-driven (one pass, per-record bundles); media bytes dump incrementally
beside the JSON. Categories are collected from entity values and assigned
deterministic ids (alphabetical), fixing the v1 exporter that emitted an empty
categories list. Pixano string ids ride along as ``pixano_id`` extensions so
the export is traceable back to its source rows.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from pixano.datasets.dataset import Dataset

from ...errors import SpecValidationError
from ...reader import RecordBundleReader


_KEYPOINT_VISIBILITY = {"invisible": 0, "hidden": 1, "visible": 2}


class CocoExporter:
    """Streams a dataset to the COCO instances layout, one JSON per split."""

    def __init__(self, media: Literal["files", "uris"] = "files", reader: RecordBundleReader | None = None):
        """Configure the export media policy."""
        self.media = media
        self.reader = reader or RecordBundleReader()

    def export(self, dataset: Dataset, destination: Path) -> Path:
        """Export the dataset; returns the destination directory."""
        destination.mkdir(parents=True, exist_ok=True)
        splits: dict[str, dict[str, list[dict]]] = defaultdict(lambda: {"images": [], "annotations": []})
        category_names: dict[str, str] = {}  # name -> supercategory
        image_ordinals: dict[str, int] = defaultdict(int)
        annotation_ordinals: dict[str, int] = defaultdict(int)

        for bundle in self.reader.iter_bundles(dataset):
            split = bundle.record.split
            image_rows = bundle.components.get("images", [])
            if not image_rows:
                continue
            image_row = image_rows[0]
            image_ordinals[split] += 1
            image_id = image_ordinals[split]
            file_name = self._media_ref(image_row, destination, split)
            splits[split]["images"].append(
                {
                    "id": image_id,
                    "file_name": file_name,
                    "width": image_row.width,
                    "height": image_row.height,
                    "pixano_id": bundle.record_id,
                    **({"coco_url": image_row.uri} if image_row.uri else {}),
                }
            )

            entities = {row.id: row for row in bundle.components.get("entities", [])}
            annotations_by_entity: dict[str, dict[str, Any]] = {}

            def entry(entity_id: str) -> dict[str, Any]:
                if entity_id not in annotations_by_entity:
                    annotation_ordinals[split] += 1
                    entity = entities.get(entity_id)
                    category = str(getattr(entity, "category", "") or "") if entity else ""
                    if category:
                        category_names.setdefault(category, str(getattr(entity, "supercategory", "") or category))
                    annotations_by_entity[entity_id] = {
                        "id": annotation_ordinals[split],
                        "image_id": image_id,
                        "iscrowd": int(bool(getattr(entity, "iscrowd", False))) if entity else 0,
                        "pixano_id": entity_id,
                        "_category": category,
                    }
                return annotations_by_entity[entity_id]

            width, height = image_row.width or 1, image_row.height or 1
            for box in bundle.components.get("bboxes", []):
                x, y, w, h = box.coords
                if box.is_normalized:
                    x, y, w, h = x * width, y * height, w * width, h * height
                entry(box.entity_id)["bbox"] = [round(v, 2) for v in (x, y, w, h)]
                entry(box.entity_id)["area"] = round(w * h, 2)
            for mask in bundle.components.get("masks", []):
                counts = mask.counts.decode("utf-8") if isinstance(mask.counts, bytes) else mask.counts
                entry(mask.entity_id)["segmentation"] = {"size": list(mask.size), "counts": counts}
            for keypoints in bundle.components.get("keypoints", []):
                flat: list[float] = []
                for index, state in enumerate(keypoints.states):
                    flat.extend(
                        [
                            round(keypoints.coords[2 * index] * width, 2),
                            round(keypoints.coords[2 * index + 1] * height, 2),
                            _KEYPOINT_VISIBILITY.get(state, 0),
                        ]
                    )
                entry(keypoints.entity_id)["keypoints"] = flat
                entry(keypoints.entity_id)["num_keypoints"] = sum(
                    1 for state in keypoints.states if state != "invisible"
                )
            splits[split]["annotations"].extend(annotations_by_entity.values())

        category_ids = {name: index for index, name in enumerate(sorted(category_names), start=1)}
        categories = [
            {"id": category_ids[name], "name": name, "supercategory": category_names[name]}
            for name in sorted(category_names)
        ]
        for split, payload in splits.items():
            for annotation in payload["annotations"]:
                annotation["category_id"] = category_ids.get(annotation.pop("_category"), 0)
            document = {
                "info": {"description": dataset.info.name, "version": "pixano-export"},
                "images": payload["images"],
                "annotations": payload["annotations"],
                "categories": categories,
            }
            (destination / f"instances_{split}.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
        return destination

    def _media_ref(self, image_row: Any, destination: Path, split: str) -> str:
        raw_bytes = getattr(image_row, "raw_bytes", b"")
        if raw_bytes:
            if self.media == "uris":
                raise SpecValidationError(
                    "media='uris' cannot export embedded media; use media='files' to dump bytes beside the JSON."
                )
            extension = (getattr(image_row, "format", "") or "bin").lower()
            file_name = f"{image_row.id}.{extension}"
            target = destination / "image" / split / file_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw_bytes)
            return file_name
        return Path(str(image_row.uri)).name or f"{image_row.id}.bin"
