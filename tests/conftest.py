# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Shared pytest configuration for the v2 test surface."""

import os

import pytest


# A developer running the stack has these exported. Read from the environment by every `Settings`,
# they would have an import queue real jobs on the stack's queue: the tests that need a queue reach
# it through PIXANO_TEST_DATABASE_URL, and set what they need.
DEPLOYMENT_VARIABLES = ("PIXANO_DATABASE_URL", "PIXANO_EMBEDDINGS_AFTER_IMPORT", "PIXANO_EMBEDDINGS_MODEL")

# Removed as the test session loads, before any plugin imports the application — whose module builds
# a `Settings` when imported — and before fixtures of any scope run.
for _variable in DEPLOYMENT_VARIABLES:
    os.environ.pop(_variable, None)


@pytest.fixture(autouse=True)
def _no_deployment_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts without them, whatever an earlier test set without undoing it."""
    for name in DEPLOYMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


pytest_plugins = [
    "tests.fixtures.datasets.dataset_info",
    "tests.fixtures.datasets.dataset_item",
    "tests.fixtures.datasets.dataset",
    "tests.fixtures.datasets.builders.builder",
    "tests.fixtures.features.bbox",
    "tests.fixtures.features.compressed_rle",
    "tests.fixtures.features.embedding",
    "tests.fixtures.features.entity",
    "tests.fixtures.features.sequence_frame",
    "tests.fixtures.inference.client",
    "tests.fixtures.job_queue",
]
