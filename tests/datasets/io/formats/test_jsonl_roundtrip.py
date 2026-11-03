# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import shutil
from pathlib import Path

import pytest
import yaml

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.io import ImportSpec, SpecValidationError, export_dataset, ffprobe_available, import_dataset
from pixano.datasets.io.formats.pixano_jsonl import PixanoJsonlImporter
from pixano.datasets.io.reader import RecordBundleReader
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, EntityDynamicState, Image, Record, Relation, Tracklet
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL
from tests.datasets.io._review_fixture import (
    DROPPED_ANNOTATIONS,
    DROPPED_ENTITIES,
    KEPT_ANNOTATIONS,
    KEPT_ENTITIES,
    KEPT_RELATIONS,
    KEPT_STATES,
    build_review_dataset,
)
from tests.datasets.io.formats.test_jsonl_importer import EXPECTED_COUNTS, NEEDS_FFPROBE, SPECS, materialize_corpus


def _sorted_ids(dataset: Dataset) -> dict[str, list[str]]:
    return {
        name: sorted(row["id"] for row in dataset.open_table(name).search().select(["id"]).limit(None).to_list())
        for name in dataset.info.tables
    }


def _import(source: Path, data_dir: Path, name: str, spec_overrides: dict | None = None) -> Dataset:
    payload = {**SPECS[name], "ids": {"namespace": name}, **(spec_overrides or {})}
    spec = ImportSpec.model_validate(payload)
    result = import_dataset(source, data_dir, spec, importer=PixanoJsonlImporter())
    return Dataset(result.dataset_path)


ROUND_TRIP_CORPORA = sorted(SPECS)


class TestGoldenRoundTrips:
    @pytest.mark.parametrize("name", ROUND_TRIP_CORPORA)
    def test_import_export_reimport_is_id_equal(self, name: str, tmp_path: Path):
        if name in NEEDS_FFPROBE and not ffprobe_available():
            pytest.skip("ffprobe not installed")

        source = materialize_corpus(name, tmp_path / "src")
        first = _import(source, tmp_path / "data1", name)

        media = "uris" if first.info.storage_mode == "filesystem" else "files"
        exported = export_dataset(first, tmp_path / "exported", media=media)

        second = _import(exported, tmp_path / "data2", name)

        assert _sorted_ids(second) == _sorted_ids(first)  # the id-equal round-trip contract (spec §5)
        for table_name, expected in EXPECTED_COUNTS[name].items():
            assert second.open_table(table_name).count_rows() == expected

    def test_exported_yaml_is_a_valid_spec(self, tmp_path: Path):
        source = materialize_corpus("voc_like", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "voc_like")
        exported = export_dataset(dataset, tmp_path / "exported")

        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        assert spec.format == "pixano_jsonl"
        from pixano.datasets.io.spec import resolve_dataset_info

        recompiled = resolve_dataset_info(spec)
        assert set(recompiled.tables) == set(dataset.info.tables)
        assert "license" in recompiled.record.model_fields  # custom attrs survive the yaml

    def test_annotation_values_survive(self, tmp_path: Path):
        source = materialize_corpus("voc_like", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "voc_like")
        exported = export_dataset(first, tmp_path / "exported")
        second = _import(exported, tmp_path / "data2", "voc_like")

        original = first.get_data("bboxes")[0]
        reimported = second.get_data("bboxes")[0]
        assert reimported.coords == original.coords
        assert reimported.format == original.format
        assert reimported.is_normalized == original.is_normalized
        assert second.get_data("masks")[0].counts == first.get_data("masks")[0].counts
        assert second.get_data("records")[0].license == "voc2007"

    def test_annotation_attrs_survive(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "mel")
        exported = export_dataset(first, tmp_path / "exported")
        second = _import(exported, tmp_path / "data2", "mel")

        original_bbox = first.get_data("bboxes")[0]
        reimported_bbox = second.get_data("bboxes")[0]
        assert reimported_bbox.annotator == original_bbox.annotator == "alice"

        original_span = first.get_data("text_spans")[0]
        reimported_span = second.get_data("text_spans")[0]
        assert reimported_span.role == original_span.role == "title"

    def test_uris_mode_refuses_embedded_dataset(self, tmp_path: Path):
        from pixano.datasets.io import SpecValidationError

        source = materialize_corpus("voc_like", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "voc_like")
        with pytest.raises(SpecValidationError, match="files"):
            export_dataset(dataset, tmp_path / "exported", media="uris")

    def test_export_includes_record_base_fields(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "mel")

        exported = export_dataset(
            first,
            tmp_path / "exported",
            media="files",
            options={"include_record_fields": ["status", "created_at"]},
        )

        # Check the exported JSONL contains status and created_at in attrs
        jsonl_path = exported / "train" / "metadata.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        # First line is the header, second line is the record
        record_line = json.loads(lines[1])
        assert "attrs" in record_line
        assert record_line["attrs"]["status"] == "new"
        assert "created_at" in record_line["attrs"]

        # Re-import and verify the values survive the round-trip EXACTLY —
        # including timestamps (fresh imports must not restamp created_at).
        second = _import(exported, tmp_path / "data2", "mel")
        original = first.get_data("records")[0]
        rec = second.get_data("records")[0]
        assert rec.status == original.status
        assert rec.created_at == original.created_at

    def test_export_excludes_record_base_fields_by_default(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        first = _import(source, tmp_path / "data1", "mel")

        exported = export_dataset(first, tmp_path / "exported", media="files")

        # Default export should NOT include status/created_at in attrs
        jsonl_path = exported / "train" / "metadata.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        record_line = json.loads(lines[1])
        attrs = record_line.get("attrs", {})
        assert "status" not in attrs
        assert "created_at" not in attrs

    def test_exported_yaml_contains_export_options(self, tmp_path: Path):
        source = materialize_corpus("mel", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "mel")
        exported = export_dataset(
            dataset,
            tmp_path / "exported",
            options={"include_record_fields": ["status", "created_at"]},
        )
        yaml_content = (exported / "dataset.yaml").read_text()
        assert "include_record_fields" in yaml_content
        assert "status" in yaml_content
        assert "created_at" in yaml_content

        # The exported yaml must remain a VALID import spec (the option lives
        # under `options`, never as an unknown top-level key), and the export
        # must be fully re-importable as-is — the §5 round-trip contract.
        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        assert spec.options["include_record_fields"] == ["status", "created_at"]
        second = _import(exported, tmp_path / "data2", "mel")
        assert _sorted_ids(second) == _sorted_ids(dataset)

    def test_hand_authored_timestamps_are_preserved(self, tmp_path: Path):
        import shutil
        from datetime import datetime

        from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL

        split = tmp_path / "src" / "train"
        split.mkdir(parents=True)
        shutil.copy(IMAGE_JPG_ASSET_URL, split / "a.jpg")
        split.joinpath("metadata.jsonl").write_text(
            '{"id": "rec_1", "attrs": {"created_at": "2020-01-02T03:04:05", "status": "validated"}, '
            '"views": {"image": "a.jpg"}}\n',
            encoding="utf-8",
        )
        spec = ImportSpec.model_validate({"format": "pixano_jsonl", "dataset": {"name": "ts", "workspace": "image"}})
        result = import_dataset(tmp_path / "src", tmp_path / "data", spec, importer=PixanoJsonlImporter())
        rec = Dataset(result.dataset_path).get_data("records")[0]
        assert rec.created_at == datetime(2020, 1, 2, 3, 4, 5)
        assert rec.status == "validated"


REVIEWED = ["accepted"]


def _record_line(exported: Path) -> dict:
    """The review fixture's one record line (line 1 is the header)."""
    lines = (exported / "train" / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads(lines[1])


def _entities(line: dict) -> dict[str, dict]:
    return {entity["id"]: entity for entity in line.get("entities", [])}


def _annotation_ids(line: dict) -> set[str]:
    return {annotation["id"] for entity in line.get("entities", []) for annotation in entity.get("annotations", [])}


class TestExportByReviewStatus:
    """An export keeps the model annotations of the selected review statuses (spec amendment 2026-10-05)."""

    @pytest.fixture()
    def review_dataset(self, tmp_path: Path) -> Dataset:
        return build_review_dataset(tmp_path / "review_ds")

    def test_keeps_annotations_no_model_produced_and_the_selected_ones(self, review_dataset: Dataset, tmp_path: Path):
        line = _record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=REVIEWED))

        assert _annotation_ids(line) == KEPT_ANNOTATIONS
        assert set(_entities(line)) == KEPT_ENTITIES

    def test_an_emptied_entity_leaves_with_its_states(self, review_dataset: Dataset, tmp_path: Path):
        entities = _entities(_record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=REVIEWED)))

        assert not DROPPED_ENTITIES & set(entities)
        # e_mixed lost its pending box but kept its accepted mask: it stays, and so does its state.
        assert [annotation["id"] for annotation in entities["e_mixed"]["annotations"]] == ["m_mixed_accepted"]
        assert sum(len(entity.get("states", [])) for entity in entities.values()) == len(KEPT_STATES)
        assert entities["e_mixed"]["states"]

    def test_an_entity_that_never_had_annotations_stays(self, review_dataset: Dataset, tmp_path: Path):
        entities = _entities(_record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=REVIEWED)))

        assert entities["e_bare"] == {"id": "e_bare", "attrs": {"category": "tree"}}

    def test_a_kept_entity_keeps_its_parents(self, review_dataset: Dataset, tmp_path: Path):
        entities = _entities(_record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=REVIEWED)))

        # Their only boxes are pending, but e_child is kept and names e_parent, which names e_grandparent.
        assert entities["e_child"]["parent_id"] == "e_parent"
        assert entities["e_parent"]["parent_id"] == "e_grandparent"
        assert "annotations" not in entities["e_parent"]
        assert "annotations" not in entities["e_grandparent"]
        # A dropped child protects nothing.
        assert "e_lone_parent" not in entities

    def test_a_kept_relation_keeps_the_entity_it_points_at(self, review_dataset: Dataset, tmp_path: Path):
        entities = _entities(_record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=REVIEWED)))

        # r_human points at e_related's pending box, r_model_pending at e_pending's.
        assert "e_related" in entities
        assert "annotations" not in entities["e_related"]
        # No person can review a relation: the model's, although pending, is kept, and protects.
        assert "e_pending" in entities
        assert "annotations" not in entities["e_pending"]

    def test_the_filtered_export_reimports(self, review_dataset: Dataset, tmp_path: Path):
        exported = export_dataset(review_dataset, tmp_path / "out", review_statuses=REVIEWED)

        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        reimported = Dataset(
            import_dataset(exported, tmp_path / "data", spec, importer=PixanoJsonlImporter()).dataset_path
        )

        ids = _sorted_ids(reimported)
        assert set(ids["entities"]) == KEPT_ENTITIES
        assert set(ids["bboxes"]) | set(ids["masks"]) == KEPT_ANNOTATIONS
        assert len(ids["entity_dynamic_states"]) == len(KEPT_STATES)
        assert {row.id: row.parent_id for row in reimported.get_data("entities") if row.parent_id} == {
            "e_child": "e_parent",
            "e_parent": "e_grandparent",
        }

    def test_dataset_yaml_records_the_selection_in_declaration_order(self, review_dataset: Dataset, tmp_path: Path):
        exported = export_dataset(
            review_dataset, tmp_path / "out", review_statuses=["accepted", "pending", "accepted"]
        )

        spec = ImportSpec.from_yaml(exported / "dataset.yaml")  # still a valid import spec
        assert spec.options == {"review_statuses": ["pending", "accepted"]}

    def test_dataset_yaml_records_the_selection_beside_the_format_options(
        self, review_dataset: Dataset, tmp_path: Path
    ):
        exported = export_dataset(
            review_dataset,
            tmp_path / "out",
            options={"include_record_fields": ["status"]},
            review_statuses=["accepted"],
        )

        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        assert spec.options == {"include_record_fields": ["status"], "review_statuses": ["accepted"]}

    def test_a_model_annotation_without_status_counts_as_pending(self, review_dataset: Dataset, tmp_path: Path):
        line = _record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=["pending"]))

        assert {"b_pending", "b_reimported"} <= _annotation_ids(line)
        assert not {"b_accepted", "m_mixed_accepted"} & _annotation_ids(line)

    def test_the_selection_applies_to_every_annotation_kind(self, review_dataset: Dataset, tmp_path: Path):
        line = _record_line(export_dataset(review_dataset, tmp_path / "out", review_statuses=["pending"]))

        mixed = _entities(line)["e_mixed"]
        assert [annotation["id"] for annotation in mixed["annotations"]] == ["b_mixed_pending"]
        assert "m_mixed_accepted" not in _annotation_ids(line)

    def test_no_selection_exports_every_row(self, review_dataset: Dataset, tmp_path: Path):
        exported = export_dataset(review_dataset, tmp_path / "out")

        line = _record_line(exported)
        assert set(_entities(line)) == KEPT_ENTITIES | DROPPED_ENTITIES
        assert _annotation_ids(line) == KEPT_ANNOTATIONS | DROPPED_ANNOTATIONS
        assert "options" not in yaml.safe_load((exported / "dataset.yaml").read_text(encoding="utf-8"))

    def test_selecting_every_status_writes_the_lines_of_no_selection(self, review_dataset: Dataset, tmp_path: Path):
        unfiltered = export_dataset(review_dataset, tmp_path / "unfiltered")
        everything = export_dataset(review_dataset, tmp_path / "everything", review_statuses=["pending", "accepted"])

        metadata = Path("train") / "metadata.jsonl"
        assert (everything / metadata).read_bytes() == (unfiltered / metadata).read_bytes()

    # A reject deletes the row, and a saved edit accepts it: neither "rejected" nor "corrected" is a status.
    @pytest.mark.parametrize("status", ["bogus", "", "Accepted", "corrected", "rejected"])
    def test_an_unknown_status_is_refused_before_writing(self, review_dataset: Dataset, tmp_path: Path, status: str):
        with pytest.raises(SpecValidationError, match="review_statuses"):
            export_dataset(review_dataset, tmp_path / "out", review_statuses=[status])
        assert not (tmp_path / "out").exists()

    def test_the_selection_is_not_a_format_option(self, review_dataset: Dataset, tmp_path: Path):
        # An exported dataset.yaml records it under `options`; copied back there, it must not pass silently.
        with pytest.raises(SpecValidationError, match="not a format option"):
            export_dataset(review_dataset, tmp_path / "out", options={"review_statuses": REVIEWED})


# A model's output stored as the JSONL importer stores it: the header's default source, and no
# review status, since the grammar carries none.
MODEL_HEADER = {"$pixano": "jsonl/2", "defaults": {"source": {"type": "model", "name": "detector"}}}


def _with_model_header(source: Path) -> Path:
    """A corpus whose rows a model produced: its lines under a header giving every row that source."""
    metadata = source / "train" / "metadata.jsonl"
    metadata.write_text(json.dumps(MODEL_HEADER) + "\n" + metadata.read_text(encoding="utf-8"), encoding="utf-8")
    return source


def _set_statuses(dataset: Dataset, table_name: str, statuses: dict[str, str]) -> None:
    """Store review decisions on a table's rows, by row id."""
    rows = dataset.get_data(table_name, ids=list(statuses))
    for row in rows:
        row.review_status = statuses[row.id]
    dataset.update_data(table_name, rows)


TRACK_SPEC = {
    "dataset": {"name": "tracks", "workspace": "video"},
    "schema": {
        "views": {"camera": {"kind": "sequence_frames"}},
        "entity": {"attrs": {"category": "str"}},
        "annotations": ["bbox", "tracklet"],
    },
    "ids": {"namespace": "tracks"},
}
FRAME_COUNT = 2


def _track_source(source: Path) -> Path:
    """Two objects tracked by a model across two frames: e_bear and e_fox, each with its tracklet."""
    frames = source / "train" / "frames"
    frames.mkdir(parents=True)
    for frame_index in range(FRAME_COUNT):
        shutil.copy(IMAGE_JPG_ASSET_URL, frames / f"{frame_index:05d}.jpg")

    def tracked(name: str) -> dict:
        return {
            "id": f"e_{name}",
            "attrs": {"category": name},
            "tracklets": [{"id": f"t_{name}", "view": "camera", "start_timestep": 0, "end_timestep": FRAME_COUNT - 1}],
            "annotations": [
                {
                    "id": f"b_{name}_{frame_index}",
                    "kind": "bbox",
                    "view": "camera",
                    "frame_index": frame_index,
                    "coords": [0.1, 0.2, 0.3, 0.4],
                    "format": "xywh",
                    "is_normalized": True,
                }
                for frame_index in range(FRAME_COUNT)
            ],
        }

    line = {
        "id": "rec",
        "views": {
            "camera": {
                "frames": [
                    {"uri": f"frames/{frame_index:05d}.jpg", "frame_index": frame_index}
                    for frame_index in range(FRAME_COUNT)
                ],
                "fps": 24,
            }
        },
        "entities": [tracked("bear"), tracked("fox")],
    }
    metadata = source / "train" / "metadata.jsonl"
    metadata.write_text(json.dumps(MODEL_HEADER) + "\n" + json.dumps(line) + "\n", encoding="utf-8")
    return source


class TestExportByReviewStatusKeepsWhatNobodyReviews:
    """The selection filters only the kinds a person can review (`is_reviewable_annotation`)."""

    def test_a_tracklet_stays_with_its_entity(self, tmp_path: Path):
        """A tracklet is the span of an object across frames, which its kept boxes still name. It
        was filtered as a pending model row, and the re-import derived another under a new id."""
        spec = ImportSpec.model_validate(TRACK_SPEC)
        source = _track_source(tmp_path / "src")
        dataset = Dataset(import_dataset(source, tmp_path / "data", spec).dataset_path)
        assert {(row.id, row.source_type, row.review_status) for row in dataset.get_data("tracklets")} == {
            ("t_bear", "model", ""),
            ("t_fox", "model", ""),
        }
        _set_statuses(
            dataset,
            "bboxes",
            {
                **dict.fromkeys(["b_bear_0", "b_bear_1"], "accepted"),
                **dict.fromkeys(["b_fox_0", "b_fox_1"], "pending"),
            },
        )

        exported = export_dataset(dataset, tmp_path / "out", review_statuses=["accepted"])
        reimported = Dataset(import_dataset(exported, tmp_path / "again", spec).dataset_path)

        # The fox lost every box, so it goes, and its tracklet with it.
        assert [row.id for row in reimported.get_data("tracklets")] == ["t_bear"]
        assert {row.id: row.tracklet_id for row in reimported.get_data("bboxes")} == {
            "b_bear_0": "t_bear",
            "b_bear_1": "t_bear",
        }

    @pytest.mark.parametrize("source_type", ["other", "ground_truth"])
    def test_a_tracklet_no_model_produced_keeps_its_entity(self, tmp_path: Path, source_type: str):
        """Every annotation no model produced is exported. The legacy interface's tracking makes the
        tracklet as the person's ('other') and every mask as the model's; a plain export and re-import
        stamps the tracklet ground truth. The fox's tracklet went with the fox once its boxes were
        left out."""
        spec = ImportSpec.model_validate(TRACK_SPEC)
        dataset = Dataset(import_dataset(_track_source(tmp_path / "src"), tmp_path / "data", spec).dataset_path)
        (fox_track,) = dataset.get_data("tracklets", ids=["t_fox"])
        fox_track.source_type = source_type
        dataset.update_data("tracklets", [fox_track])
        _set_statuses(
            dataset,
            "bboxes",
            {
                **dict.fromkeys(["b_bear_0", "b_bear_1"], "accepted"),
                **dict.fromkeys(["b_fox_0", "b_fox_1"], "pending"),
            },
        )

        exported = export_dataset(dataset, tmp_path / "out", review_statuses=["accepted"])
        reimported = Dataset(import_dataset(exported, tmp_path / "again", spec).dataset_path)

        assert sorted(row.id for row in reimported.get_data("tracklets")) == ["t_bear", "t_fox"]
        assert sorted(row.id for row in reimported.get_data("entities")) == ["e_bear", "e_fox"]
        assert sorted(row.id for row in reimported.get_data("bboxes")) == ["b_bear_0", "b_bear_1"]

    def test_a_text_span_is_kept_whatever_its_status(self, tmp_path: Path):
        """No interface shows a text span for review: nobody could have accepted it."""
        source = _with_model_header(materialize_corpus("mel", tmp_path / "src"))
        dataset = _import(source, tmp_path / "data", "mel")
        (box,) = dataset.get_data("bboxes")
        (span,) = dataset.get_data("text_spans")
        assert (span.source_type, span.review_status) == ("model", "")
        _set_statuses(dataset, "bboxes", {box.id: "accepted"})

        line = _record_line(export_dataset(dataset, tmp_path / "out", review_statuses=["accepted"]))

        assert _annotation_ids(line) == {box.id, span.id}


def _tracked_object_with_a_relation(path: Path, tracklet_source: str) -> Dataset:
    """An object whose only box is pending, with its tracklet and dynamic state, and a person's
    relation from their own box to the object's tracklet."""
    dataset = Dataset.create(
        path,
        DatasetInfo(
            name="relation_ds",
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            entity_dynamic_state=EntityDynamicState,
            bbox=BBox,
            tracklet=Tracklet,
            relation=Relation,
            views={"image": Image},
        ),
    )

    def box(box_id: str, entity_id: str, source_type: str, review_status: str = "") -> BBox:
        return BBox(
            id=box_id,
            record_id="rec",
            view_id="img",
            entity_id=entity_id,
            coords=[0.1, 0.1, 0.2, 0.2],
            format="xywh",
            is_normalized=True,
            source_type=source_type,
            review_status=review_status,
        )

    dataset.add_records(
        {
            "records": [Record(id="rec", split="train")],
            "images": [Image(id="img", record_id="rec", logical_name="image", uri="img.jpg", width=8, height=8)],
            "entities": [Entity(id="e_obj", record_id="rec"), Entity(id="e_person", record_id="rec")],
            "entity_dynamic_states": [
                EntityDynamicState(id="s_obj", record_id="rec", entity_id="e_obj", view_id="img")
            ],
            "bboxes": [box("b_obj", "e_obj", "model", "pending"), box("b_person", "e_person", "human")],
            "tracklets": [
                Tracklet(
                    id="t_obj",
                    record_id="rec",
                    view_id="img",
                    entity_id="e_obj",
                    start_timestep=0,
                    end_timestep=1,
                    source_type=tracklet_source,
                )
            ],
            "relations": [
                Relation(
                    id="r_follows",
                    record_id="rec",
                    view_id="img",
                    predicate="follows",
                    subject_id="b_person",
                    object_id="t_obj",
                    source_type="human",
                )
            ],
        }
    )
    return dataset


class TestReaderGuarantees:
    def test_review_selection_adds_no_query(self, tmp_path: Path):
        dataset = build_review_dataset(tmp_path / "review_ds")

        unfiltered: list[str] = []
        filtered: list[str] = []
        list(RecordBundleReader(query_counter=unfiltered.append).iter_bundles(dataset))
        list(RecordBundleReader(query_counter=filtered.append, review_statuses=REVIEWED).iter_bundles(dataset))

        assert filtered == unfiltered

    def test_review_selection_keeps_relations_and_drops_states_with_their_entity(self, tmp_path: Path):
        # Neither exporter writes relations; the reader still hands every consumer the same selection.
        dataset = build_review_dataset(tmp_path / "review_ds")

        (bundle,) = RecordBundleReader(review_statuses=REVIEWED).iter_bundles(dataset)

        assert {row.id for row in bundle.components["relations"]} == KEPT_RELATIONS
        assert {row.id for row in bundle.components["entity_dynamic_states"]} == KEPT_STATES

    @pytest.mark.parametrize("source_type", ["model", "human"])
    def test_a_kept_relation_naming_a_tracklet_keeps_its_entity(self, tmp_path: Path, source_type: str):
        """A relation links annotations, a tracklet among them (`utils/integrity.py`): it protects
        the entity of what it names. Naming the object's pending box kept the object, its tracklet
        and its states; naming its tracklet kept none of them."""
        dataset = _tracked_object_with_a_relation(tmp_path / "relation_ds", source_type)

        (bundle,) = RecordBundleReader(review_statuses=REVIEWED).iter_bundles(dataset)

        assert {row.id for row in bundle.components["entities"]} == {"e_obj", "e_person"}
        assert [row.id for row in bundle.components["tracklets"]] == ["t_obj"]
        assert [row.id for row in bundle.components["entity_dynamic_states"]] == ["s_obj"]
        assert [row.id for row in bundle.components["relations"]] == ["r_follows"]
        assert [row.id for row in bundle.components["bboxes"]] == ["b_person"]

    @pytest.mark.parametrize("status", ["bogus", "", "corrected", "rejected"])
    def test_reader_refuses_an_unknown_status(self, status: str):
        with pytest.raises(ValueError):
            RecordBundleReader(review_statuses=[status])

    def test_no_per_record_queries(self, tmp_path: Path):
        source = materialize_corpus("multiview", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "multiview")

        queries: list[str] = []
        reader = RecordBundleReader(page_size=8, query_counter=queries.append)
        bundles = list(reader.iter_bundles(dataset))

        assert len(bundles) == 1
        # 1 ids scan + 1 record page + at most a few sub-batches per component table —
        # bounded by tables, never by records.
        assert len(queries) <= 2 + 2 * len(dataset.info.tables)

    def test_bytes_in_flight_shrinks_blob_batches(self, tmp_path: Path):
        source = materialize_corpus("multiview", tmp_path / "src")
        dataset = _import(source, tmp_path / "data", "multiview")

        queries: list[str] = []
        # Budget below one image's size: image sub-batches must fall to size 1.
        reader = RecordBundleReader(max_bytes_in_flight=1_000, initial_blob_batch=64, query_counter=queries.append)
        bundles = list(reader.iter_bundles(dataset))
        assert bundles[0].components["images"] and len(bundles[0].components["images"]) == 2

    def test_completeness_on_fixture_dataset(self, dataset_multi_view_tracking_and_image: Dataset):
        reader = RecordBundleReader(page_size=3)
        bundles = list(reader.iter_bundles(dataset_multi_view_tracking_and_image))
        record_count = dataset_multi_view_tracking_and_image.open_table("records").count_rows()
        assert len(bundles) == record_count
        assert sorted({bundle.record_id for bundle in bundles}) == sorted(
            row["id"]
            for row in dataset_multi_view_tracking_and_image.open_table("records")
            .search()
            .select(["id"])
            .limit(None)
            .to_list()
        )
        total_components = sum(len(rows) for bundle in bundles for rows in bundle.components.values())
        expected_components = sum(
            dataset_multi_view_tracking_and_image.open_table(name).count_rows()
            for name in dataset_multi_view_tracking_and_image.info.tables
            if name not in ("records", "embeddings")
        )
        assert total_components >= expected_components - _embedding_rows(dataset_multi_view_tracking_and_image)


def _embedding_rows(dataset: Dataset) -> int:
    total = 0
    for name in dataset.info.tables:
        if "embedding" in name:
            total += dataset.open_table(name).count_rows()
    return total
