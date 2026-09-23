# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Kill-9 test helper: runs a toy import, signalling and stalling at the first checkpoint.

Usage: python _import_main.py <data_dir> <marker_file>

The parent test waits for <marker_file>, then SIGKILLs this process while the
staged build is mid-flight — the library must remain untouched.
"""

import sys
import time
from pathlib import Path

from pixano.datasets.io import ImportEngine, ImportSpec, import_dataset
from pixano.datasets.io.spec import workspace_preset
from pixano.datasets.workspaces import WorkspaceType
from tests.datasets.io._toy_importer import ToyImporter


def main() -> None:
    data_dir = Path(sys.argv[1])
    marker_file = Path(sys.argv[2])

    def checkpoint(cursor, table_counts) -> None:
        marker_file.write_text(str(cursor))
        time.sleep(120)  # stall inside the build so the parent can SIGKILL us

    spec = ImportSpec.model_validate({"dataset": {"name": "killed_ds", "workspace": "image"}, "format": "toy"})
    info = workspace_preset(WorkspaceType.IMAGE)
    import_dataset(
        "unused-source",
        data_dir,
        spec,
        importer=ToyImporter(num_records=64, batch_size=4),
        info=info,
        engine=ImportEngine(data_dir, flush_rows=8, checkpoint=checkpoint),
    )


if __name__ == "__main__":
    main()
