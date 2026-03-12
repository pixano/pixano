"""Shared pytest configuration for the v2 test surface."""

pytest_plugins = [
    "tests.fixtures.datasets.dataset_info",
    "tests.fixtures.datasets.dataset_item",
    "tests.fixtures.datasets.dataset",
    "tests.fixtures.datasets.builders.builder",
    "tests.fixtures.datasets.builders.folder",
    "tests.fixtures.features.bbox",
    "tests.fixtures.features.compressed_rle",
    "tests.fixtures.features.embedding",
    "tests.fixtures.features.entity",
    "tests.fixtures.features.sequence_frame",
    "tests.fixtures.inference.client",
]
