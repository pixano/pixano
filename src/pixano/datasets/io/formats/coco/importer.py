# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The COCO importer: two-pass streaming over instances JSON files (spec §7.2).

Pass 1 streams ``annotations`` into an index keyed by ``image_id`` (SQLite
spill above a row threshold, so annotation files larger than RAM import in
bounded memory); pass 2 streams ``images`` joining that index. `ijson` (the
``coco`` extra) enables true streaming; without it the file is loaded whole,
flagged by a Finding at analyze — never silently.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterator

from lancedb.pydantic import LanceModel

from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import CompressedRLE

from ...errors import MetadataError
from ...ids import stable_id
from ...importer import BatchBundle, Cursor, DatasetImporter, DetectResult, SourceRef
from ...media import MediaResolver, probe_image
from ...plan import AnalyzeLimits, ImportPlan, Provenance, SamplePreview
from ...registry import Capabilities, DataFormat
from ...spec import ImportSpec, resolve_dataset_info


_COCO_KEYPOINT_STATES = {0: "invisible", 1: "hidden", 2: "visible"}
_COCO17_TEMPLATE_ID = "coco-17"
_SPILL_THRESHOLD = 500_000  # annotations held in memory before spilling to SQLite

_DEFAULT_SCHEMA = {
    "entity": {
        "attrs": {
            "category": "str",
            "supercategory": "str",
            "iscrowd": {"type": "bool", "default": False},
        }
    },
    "annotations": ["bbox", "mask", "keypoint"],
}


def _find_annotation_files(source_dir: Path) -> list[tuple[str, Path]]:
    """Locate instances_*.json files; the suffix after 'instances_' is the split."""
    found: dict[str, Path] = {}
    for pattern in ("instances_*.json", "annotations/instances_*.json"):
        for path in sorted(source_dir.glob(pattern)):
            split = path.stem.removeprefix("instances_") or "train"
            found.setdefault(split, path)
    return sorted(found.items())


class _AnnotationIndex:
    """Annotations grouped by image_id: dict-backed, spilling to SQLite past a threshold."""

    def __init__(self, spill_threshold: int = _SPILL_THRESHOLD):
        """Configure the annotation-index spill threshold (rows kept in memory)."""
        self.spill_threshold = spill_threshold
        self._memory: dict[str, list[dict]] = {}
        self._count = 0
        self._db: sqlite3.Connection | None = None

    def add(self, image_id: str, annotation: dict) -> None:
        self._count += 1
        if self._db is None and self._count > self.spill_threshold:
            self._spill()
        if self._db is None:
            self._memory.setdefault(image_id, []).append(annotation)
        else:
            self._db.execute("INSERT INTO anns (image_id, payload) VALUES (?, ?)", (image_id, json.dumps(annotation)))

    def _spill(self) -> None:
        spill_file = tempfile.NamedTemporaryFile(prefix="pixano-coco-spill-", suffix=".sqlite", delete=False)
        self._db = sqlite3.connect(spill_file.name)
        self._db.execute("CREATE TABLE anns (image_id TEXT, payload TEXT)")
        self._db.execute("CREATE INDEX idx_image ON anns (image_id)")
        for image_id, spilled_annotations in self._memory.items():
            for annotation in spilled_annotations:
                self._db.execute(
                    "INSERT INTO anns (image_id, payload) VALUES (?, ?)", (image_id, json.dumps(annotation))
                )
        self._memory.clear()

    def get(self, image_id: str) -> list[dict]:
        if self._db is None:
            return self._memory.get(image_id, [])
        rows = self._db.execute("SELECT payload FROM anns WHERE image_id = ?", (image_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    @property
    def count(self) -> int:
        return self._count

    @property
    def spilled(self) -> bool:
        return self._db is not None

    def close(self) -> None:
        if self._db is not None:
            self._db.close()


def _stream_array(json_path: Path, key: str) -> tuple[Iterator[dict], bool]:
    """Stream the items of a top-level array; returns (iterator, streamed?)."""
    try:
        import ijson

        def _iter() -> Iterator[dict]:
            with json_path.open("rb") as handle:
                yield from ijson.items(handle, f"{key}.item")

        return _iter(), True
    except ImportError:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return iter(payload.get(key, [])), False


def _prefetch_media(
    numbered: "Iterator[tuple[int, dict]]", spec: ImportSpec, source_dir: Path, split: str, lookahead: int = 16
) -> "Iterator[tuple[int, dict, bytes | None]]":
    """Read image bytes ahead with a small thread pool (overlaps disk latency)."""
    if spec.media.mode != "embed":
        for ordinal, image in numbered:
            yield ordinal, image, None
        return

    from collections import deque
    from concurrent.futures import ThreadPoolExecutor

    def read(image: dict) -> bytes | None:
        local = CocoImporter._locate_image(source_dir, split, str(image.get("file_name", "")))
        return local.read_bytes() if local is not None else None

    with ThreadPoolExecutor(max_workers=8) as pool:
        window: deque = deque()
        for ordinal, image in numbered:
            window.append((ordinal, image, pool.submit(read, image)))
            if len(window) >= lookahead:
                queued_ordinal, queued_image, future = window.popleft()
                yield queued_ordinal, queued_image, future.result()
        while window:
            queued_ordinal, queued_image, future = window.popleft()
            yield queued_ordinal, queued_image, future.result()


class CocoImporter(DatasetImporter):
    """Importer for COCO instances JSON (detection, segmentation, keypoints)."""

    format_name = "coco"
    importer_version = "1.0.0"
    supports_resume = True
    deterministic_ids = True

    def __init__(self, spill_threshold: int = _SPILL_THRESHOLD):
        """Configure the annotation-index spill threshold (rows kept in memory)."""
        self.spill_threshold = spill_threshold

    # ------------------------------------------------------------------
    # Detection & schema
    # ------------------------------------------------------------------

    def probe(self, source: SourceRef) -> DetectResult | None:
        """Sniff for instances_*.json at the source root or under annotations/."""
        if source.path is None or not source.path.is_dir():
            return None
        files = _find_annotation_files(source.path)
        if files:
            return DetectResult(confidence=0.9, evidence=f"{files[0][1].name}")
        return None

    def resolve_info(self, spec: ImportSpec, source: SourceRef | None = None) -> DatasetInfo:
        """COCO has an intrinsic schema; a user-declared schema block still wins."""
        if spec.schema_ is not None or spec.schema_manifest is not None:
            return resolve_dataset_info(spec)
        payload = spec.model_dump(mode="json", exclude_none=True, by_alias=True)
        if payload.get("dataset", {}).get("workspace", "undefined") == "undefined":
            # Formats know their natural UI workspace; an explicit --workspace wins.
            payload.setdefault("dataset", {})["workspace"] = "image"
        payload["schema"] = _DEFAULT_SCHEMA
        return resolve_dataset_info(ImportSpec.model_validate(payload))

    # ------------------------------------------------------------------
    # Analyze
    # ------------------------------------------------------------------

    def analyze(self, source: SourceRef, spec: ImportSpec, limits: AnalyzeLimits) -> ImportPlan:
        """Count images/annotations per split; verify media and category references."""
        plan = ImportPlan(format=self.format_name, importer_version=self.importer_version)
        if source.path is None or not source.path.is_dir():
            plan.report.add("invalid_source", Provenance(file=source.location()), suggestion="Expected a directory.")
            return plan
        annotation_files = _find_annotation_files(source.path)
        if not annotation_files:
            plan.report.add(
                "missing_annotations",
                Provenance(file=str(source.path)),
                suggestion="No instances_*.json found at the source root or under annotations/.",
            )
            return plan

        total = 0
        media_probes = 0
        for split, json_path in annotation_files:
            categories = self._load_categories(json_path)
            provenance = Provenance(file=str(json_path))

            annotation_stream, streamed = _stream_array(json_path, "annotations")
            if not streamed:
                plan.report.add(
                    "coco_in_memory",
                    provenance,
                    severity="warning",
                    suggestion="ijson is not installed; the JSON is loaded whole. pip install pixano[coco] "
                    "for bounded-memory streaming.",
                )
            unknown_categories: set[int] = set()
            annotation_count = 0
            for annotation in annotation_stream:
                annotation_count += 1
                category_id = annotation.get("category_id")
                if category_id is not None and category_id not in categories:
                    unknown_categories.add(int(category_id))
            if unknown_categories:
                plan.report.add(
                    "unknown_category_id",
                    provenance,
                    suggestion=f"Annotations reference undeclared category ids: {sorted(unknown_categories)[:5]}.",
                )

            images, _ = _stream_array(json_path, "images")
            split_count = 0
            for image in images:
                split_count += 1
                if spec.media.mode == "embed" and media_probes < limits.max_media_probes:
                    media_probes += 1
                    if self._locate_image(source.path, split, image.get("file_name", "")) is None:
                        plan.report.add(
                            "missing_media",
                            provenance,
                            suggestion=f"Image file '{image.get('file_name')}' not found for split '{split}'.",
                        )
                if spec.media.mode == "uri" and not image.get("coco_url"):
                    plan.report.add(
                        "missing_coco_url",
                        provenance,
                        suggestion="Media mode 'uri' needs a coco_url per image; use embed for local files.",
                    )
                if len(plan.previews) < limits.max_previews:
                    plan.previews.append(SamplePreview(record={"split": split, **image}))
            plan.splits[split] = split_count
            total += split_count

        plan.totals.records = total
        return plan

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def iter_batches(
        self,
        source: SourceRef,
        spec: ImportSpec,
        plan: ImportPlan,
        cursor: Cursor | None = None,
    ) -> Iterator[BatchBundle]:
        """Two passes per split: index annotations, then stream images joining the index."""
        assert source.path is not None
        info = self.resolve_info(spec)
        namespace = self.effective_namespace(spec, source)
        resolver = MediaResolver(spec.media, base_dir=source.path)
        resume_split = cursor.get("split") if cursor else None
        resume_ordinal = int(cursor.get("image_ordinal", 0)) if cursor else 0

        for split, json_path in _find_annotation_files(source.path):
            if resume_split is not None and split < resume_split:
                continue
            categories = self._load_categories(json_path)
            index = _AnnotationIndex(self.spill_threshold)
            try:
                annotation_stream, _ = _stream_array(json_path, "annotations")
                for annotation in annotation_stream:
                    index.add(str(annotation.get("image_id", "")), annotation)

                images, _ = _stream_array(json_path, "images")
                numbered = (
                    (ordinal, image)
                    for ordinal, image in enumerate(images, start=1)
                    if not (resume_split == split and ordinal <= resume_ordinal)
                )
                for ordinal, image, media in _prefetch_media(numbered, spec, source.path, split):
                    tables = self._build_image(
                        info, spec, resolver, source.path, namespace, split, image, index, categories, media
                    )
                    yield BatchBundle(
                        tables=tables,
                        cursor={"split": split, "image_ordinal": ordinal},
                        provenance=Provenance(file=str(json_path)),
                    )
            finally:
                index.close()

    # ------------------------------------------------------------------
    # Row construction
    # ------------------------------------------------------------------

    def _build_image(
        self,
        info: DatasetInfo,
        spec: ImportSpec,
        resolver: MediaResolver,
        source_dir: Path,
        namespace: str,
        split: str,
        image: dict,
        index: _AnnotationIndex,
        categories: dict[int, dict],
        media: bytes | None = None,
    ) -> dict[str, list[LanceModel]]:
        tables: dict[str, list[LanceModel]] = {}
        image_id = str(image.get("id", ""))
        record_id = stable_id(namespace, split, image_id)
        assert info.record is not None
        tables["records"] = [info.record(id=record_id, split=split)]

        width = int(image.get("width", 0) or 0)
        height = int(image.get("height", 0) or 0)
        file_name = str(image.get("file_name", ""))
        if spec.media.mode == "uri":
            resolved_uri, raw_bytes = str(image.get("coco_url", "")), b""
        elif media is not None:
            resolved_uri, raw_bytes = "", media
        else:
            local = self._locate_image(source_dir, split, file_name)
            if local is None:
                raise MetadataError(f"Image file '{file_name}' not found for split '{split}'.")
            resolved = resolver.resolve(str(local.relative_to(source_dir)))
            resolved_uri, raw_bytes = resolved.uri, resolved.raw_bytes
        if not width or not height:
            local = self._locate_image(source_dir, split, file_name)
            if local is not None:
                width, height, _ = probe_image(local)
        view_cls = info.views["image"]
        view_id = stable_id(record_id, "view", "image")
        tables["images"] = [
            view_cls(
                id=view_id,
                record_id=record_id,
                logical_name="image",
                uri=resolved_uri,
                raw_bytes=raw_bytes,
                width=width,
                height=height,
                format=Path(file_name).suffix.removeprefix(".").upper() or "UNKNOWN",
            )
        ]

        for annotation in index.get(image_id):
            self._build_annotation(info, tables, record_id, view_id, annotation, categories, width, height)
        return tables

    def _build_annotation(
        self,
        info: DatasetInfo,
        tables: dict[str, list[LanceModel]],
        record_id: str,
        view_id: str,
        annotation: dict,
        categories: dict[int, dict],
        width: int,
        height: int,
    ) -> None:
        annotation_id = str(annotation.get("id", ""))
        category = categories.get(int(annotation.get("category_id", -1)), {})
        entity_id = stable_id(record_id, "ent", annotation_id)
        assert info.entity is not None
        tables.setdefault("entities", []).append(
            info.entity(
                id=entity_id,
                record_id=record_id,
                category=str(category.get("name", "")),
                supercategory=str(category.get("supercategory", "")),
                iscrowd=bool(annotation.get("iscrowd", 0)),
            )
        )
        common = {"record_id": record_id, "entity_id": entity_id, "view_id": view_id}

        bbox = annotation.get("bbox")
        if bbox and len(bbox) == 4 and width and height and info.bbox is not None:
            x, y, w, h = bbox
            tables.setdefault("bboxes", []).append(
                info.bbox(
                    id=stable_id(entity_id, "bbox", 0),
                    coords=[x / width, y / height, w / width, h / height],
                    format="xywh",
                    is_normalized=True,
                    confidence=1.0,
                    **common,
                )
            )

        segmentation = annotation.get("segmentation")
        if segmentation and info.mask is not None:
            rle = self._to_rle(segmentation, height, width)
            if rle is not None:
                tables.setdefault("masks", []).append(
                    info.mask(id=stable_id(entity_id, "mask", 0), size=rle.size, counts=rle.counts, **common)
                )

        keypoints = annotation.get("keypoints")
        if keypoints and width and height and info.keypoint is not None:
            coords: list[float] = []
            states: list[str] = []
            for i in range(0, len(keypoints) - 2, 3):
                coords.extend([keypoints[i] / width, keypoints[i + 1] / height])
                states.append(_COCO_KEYPOINT_STATES.get(int(keypoints[i + 2]), "invisible"))
            tables.setdefault("keypoints", []).append(
                info.keypoint(
                    id=stable_id(entity_id, "keypoints", 0),
                    template_id=_COCO17_TEMPLATE_ID,
                    coords=coords,
                    states=states,
                    **common,
                )
            )

    @staticmethod
    def _to_rle(segmentation: Any, height: int, width: int) -> CompressedRLE | None:
        if isinstance(segmentation, dict):
            counts = segmentation.get("counts")
            if isinstance(counts, list):
                return CompressedRLE.from_urle({"counts": counts, "size": segmentation.get("size", [height, width])})
            if isinstance(counts, (str, bytes)):
                counts_bytes = counts.encode("utf-8") if isinstance(counts, str) else counts
                return CompressedRLE(size=segmentation.get("size", [height, width]), counts=counts_bytes)
        if isinstance(segmentation, list) and segmentation and height and width:
            return CompressedRLE.from_polygons(segmentation, height=height, width=width)
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_categories(json_path: Path) -> dict[int, dict]:
        categories, _ = _stream_array(json_path, "categories")
        return {category["id"]: category for category in categories}

    @staticmethod
    def _locate_image(source_dir: Path, split: str, file_name: str) -> Path | None:
        if not file_name:
            return None
        for candidate in (
            source_dir / split / file_name,
            source_dir / "image" / split / file_name,
            source_dir / "images" / split / file_name,
            source_dir / file_name,
        ):
            if candidate.is_file():
                return candidate
        return None


def _detect(source: SourceRef) -> DetectResult | None:
    return CocoImporter().probe(source)


COCO = DataFormat(
    name="coco",
    title="COCO instances",
    importer_cls=CocoImporter,
    capabilities=Capabilities(
        media_kinds=frozenset({"image"}),
        annotation_kinds=frozenset({"bbox", "mask", "keypoints"}),
        source_kinds=frozenset({"local_dir"}),
        supports_resume=True,
        deterministic_ids=True,
    ),
    detect=_detect,
)
