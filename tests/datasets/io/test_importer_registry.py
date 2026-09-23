# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Iterator

import pytest

from pixano.datasets.io import (
    AnalyzeLimits,
    BatchBundle,
    DataFormat,
    DatasetImporter,
    DetectResult,
    FormatDetectionError,
    FormatRegistry,
    ImportPlan,
    SourceRef,
    SpecValidationError,
)


class _StubImporter(DatasetImporter):
    format_name = "stub"
    importer_version = "1.0.0"
    deterministic_ids = True

    def analyze(self, source, spec, limits: AnalyzeLimits) -> ImportPlan:
        return ImportPlan(format=self.format_name, importer_version=self.importer_version)

    def iter_batches(self, source, spec, plan, cursor=None) -> Iterator[BatchBundle]:
        yield BatchBundle(tables={}, cursor={"pos": 0})


def _format(name: str, confidence: float | None) -> DataFormat:
    detect = None
    if confidence is not None:
        detect = lambda source: DetectResult(confidence=confidence, evidence=f"{name} marker")  # noqa: E731
    return DataFormat(name=name, title=name.title(), importer_cls=_StubImporter, detect=detect)


class TestSourceRef:
    def test_from_string(self, tmp_path: Path):
        assert SourceRef.from_string("hub://org/repo") == SourceRef(kind="hf_hub", url="org/repo")
        assert SourceRef.from_string(str(tmp_path)).kind == "local_dir"
        assert SourceRef.from_string(str(tmp_path / "file.json")).kind == "local_file"


class TestFormatRegistry:
    def test_register_get_and_duplicate(self):
        registry = FormatRegistry(builtin=[_format("alpha", None)])
        assert registry.get("alpha").name == "alpha"
        with pytest.raises(SpecValidationError, match="already registered"):
            registry.register(_format("alpha", None))

    def test_unknown_format_lists_known(self):
        registry = FormatRegistry(builtin=[_format("alpha", None)])
        with pytest.raises(SpecValidationError, match="Unknown data format 'nope'.*alpha"):
            registry.get("nope")

    def test_detect_picks_highest_confidence(self, tmp_path: Path):
        registry = FormatRegistry(builtin=[_format("weak", 0.3), _format("strong", 0.9)])
        detected = registry.detect(SourceRef.from_string(str(tmp_path)))
        assert detected.name == "strong"

    def test_detect_tie_is_an_error(self, tmp_path: Path):
        registry = FormatRegistry(builtin=[_format("one", 0.8), _format("two", 0.8)])
        with pytest.raises(FormatDetectionError, match="Ambiguous.*one.*two"):
            registry.detect(SourceRef.from_string(str(tmp_path)))

    def test_detect_no_match_is_an_error(self, tmp_path: Path):
        registry = FormatRegistry(builtin=[_format("silent", None)])
        with pytest.raises(FormatDetectionError, match="Could not detect"):
            registry.detect(SourceRef.from_string(str(tmp_path)))

    def test_broken_detector_is_isolated(self, tmp_path: Path):
        def broken(source):
            raise RuntimeError("boom")

        registry = FormatRegistry(
            builtin=[
                DataFormat(name="broken", title="Broken", detect=broken),
                _format("healthy", 0.5),
            ]
        )
        assert registry.detect(SourceRef.from_string(str(tmp_path))).name == "healthy"

    def test_broken_entry_point_is_isolated(self, monkeypatch):
        class _BadEntryPoint:
            name = "bad"

            def load(self):
                raise ImportError("plugin exploded")

        class _GoodEntryPoint:
            name = "good"

            def load(self):
                return _format("plugin_format", None)

        monkeypatch.setattr(
            "pixano.datasets.io.registry.entry_points",
            lambda group: [_BadEntryPoint(), _GoodEntryPoint()],
        )
        registry = FormatRegistry()
        assert "plugin_format" in registry.names()
        assert "bad" not in registry.names()


class TestImporterContract:
    def test_stub_importer_round_trip(self, tmp_path: Path):
        from pixano.datasets.io import ImportSpec

        importer = _StubImporter()
        source = SourceRef.from_string(str(tmp_path))
        plan = importer.analyze(source, ImportSpec(), AnalyzeLimits())
        assert plan.format == "stub"
        bundles = list(importer.iter_batches(source, ImportSpec(), plan))
        assert bundles[0].cursor == {"pos": 0}
