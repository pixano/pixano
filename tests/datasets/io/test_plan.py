# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.io import Finding, ImportPlan, PreflightReport, Provenance
from pixano.datasets.io.errors import MetadataError
from pixano.datasets.io.plan import fingerprint


class TestProvenanceAndErrors:
    def test_location_rendering(self):
        provenance = Provenance(file="train/metadata.jsonl", line=42, json_pointer="/entities/0/annotations/1")
        assert provenance.location() == "train/metadata.jsonl:42:/entities/0/annotations/1"
        assert Provenance().location() == "<unknown>"

    def test_errors_carry_provenance(self):
        provenance = Provenance(file="train/metadata.jsonl", line=7)
        error = MetadataError("unknown annotation kind 'boxx'", provenance)
        assert "train/metadata.jsonl:7" in str(error)
        assert error.provenance is provenance


class TestPreflightReport:
    def test_aggregation_and_sample_cap(self):
        report = PreflightReport()
        for line in range(10):
            report.add("unknown_key", Provenance(file="f.jsonl", line=line), severity="warning")
        report.add("missing_view_media", Provenance(file="f.jsonl", line=3))

        assert report.warning_count == 10
        assert report.error_count == 1
        assert not report.is_valid
        assert len(report.findings["unknown_key"].samples) == 5  # capped
        assert report.findings["unknown_key"].count == 10

    def test_valid_when_only_warnings(self):
        report = PreflightReport()
        report.add("prefer_snake_case", Provenance(line=1), severity="warning")
        assert report.is_valid


class TestImportPlan:
    def test_json_round_trip(self):
        plan = ImportPlan(
            format="pixano_jsonl",
            importer_version="1.0.0",
            spec_fingerprint=fingerprint({"a": 1}),
            source_fingerprint=fingerprint(["train/metadata.jsonl", 1234]),
            splits={"train": 100, "val": None},
        )
        plan.report.add("unknown_key", Provenance(file="f.jsonl", line=1), severity="warning")

        restored = ImportPlan.model_validate_json(plan.model_dump_json())
        assert restored == plan
        assert restored.plan_fingerprint == plan.plan_fingerprint

    def test_fingerprints_are_stable_and_order_insensitive(self):
        assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})
        assert fingerprint({"a": 1}) != fingerprint({"a": 2})

    def test_finding_model_round_trip(self):
        finding = Finding(code="x", severity="error", suggestion="use v2 grammar")
        finding.add(Provenance(line=3))
        assert Finding.model_validate_json(finding.model_dump_json()) == finding
