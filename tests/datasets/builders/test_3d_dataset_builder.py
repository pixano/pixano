# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
from pathlib import Path

import lancedb
from tri3d.datasets import NuScenes

from pixano.datasets.builders import Dataset3DBuilder


def test_3d_dataset_builder():
    name = "Nuscenes tri3d"
    target_dir = f"/Path/to/target_dir{name}"
    source_dir = "path/to/nuscenes/dataset/root"

    try:
        # Remove the directory and all its contents
        shutil.rmtree(target_dir)
        print(f"Directory '{target_dir}' has been removed.")
    except Exception as e:
        print(f"Error: {e}")

    tri3d_dataset = NuScenes(source_dir, "v1.0-mini")
    builder = Dataset3DBuilder(
        target_dir=target_dir,
        source_dir=source_dir,
        dataset_name=name,
        dataset_description="Nuscenes built with tri3d",
        tri3d_dataset=tri3d_dataset,
    )
    builder.build()

    db = lancedb.connect(Path(target_dir) / "db")
    print("---------------")
    print("All tables :", ", ".join(t for t in db.list_tables().tables))
    print("---------------")

    for tname in db.list_tables().tables:
        df = db.open_table(tname).to_pandas()
        print("---------------", tname, ",", len(df), "samples", "---------------------")
        print(df.info(verbose=False))
        print(df)
