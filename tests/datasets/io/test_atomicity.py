# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import hashlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from tests.datasets.io._toy_importer import ToyImporter


REPO_ROOT = Path(__file__).parents[3]
HELPER = Path(__file__).parent / "_import_main.py"


def _tree_hash(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        hasher.update(str(path.relative_to(root)).encode())
        if path.is_file():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


class TestKillNineAtomicity:
    def test_sigkill_mid_create_leaves_library_untouched(self, tmp_path: Path):
        # Pre-existing library content that must survive byte-identically.
        spec = ImportSpec.model_validate({"dataset": {"name": "existing_ds", "workspace": "image"}, "format": "toy"})
        import_dataset("unused", tmp_path, spec, importer=ToyImporter(num_records=2))
        library = tmp_path / "library"
        hash_before = _tree_hash(library)

        marker = tmp_path / "first_flush.marker"
        process = subprocess.Popen(
            [sys.executable, str(HELPER), str(tmp_path), str(marker)],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 120
            while not marker.exists():
                assert process.poll() is None, "helper exited before reaching the first flush"
                assert time.monotonic() < deadline, "helper never reached the first flush"
                time.sleep(0.2)
            os.kill(process.pid, signal.SIGKILL)
            process.wait(timeout=30)
        finally:
            if process.poll() is None:
                process.kill()

        assert _tree_hash(library) == hash_before, "a killed staged build must not touch library/"
        assert not (library / "killed_ds").exists()

        # A rerun of the same import succeeds cleanly afterwards.
        rerun_spec = ImportSpec.model_validate(
            {"dataset": {"name": "killed_ds", "workspace": "image"}, "format": "toy"}
        )
        result = import_dataset("unused", tmp_path, rerun_spec, importer=ToyImporter(num_records=64, batch_size=4))
        assert Dataset(result.dataset_path).open_table("records").count_rows() == 64
