# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
from pathlib import Path

import lancedb
from tri3d.datasets import NuScenes

import pixano.features as pix_types
from pixano.datasets.builders import Dataset3DBuilder
from pixano.datasets.dataset_info import DatasetInfo


def test_3d_dataset_builder():
    name = "Nuscenes tri3d"
    target_dir = f"/home/mfauvel/Documents/pixano_data/library/{name}"
    info = DatasetInfo(
        name=name,
        description="Nuscenes built with tri3d",
        record=pix_types.Record,
        views={
            "CAM_FRONT": pix_types.CalibratedImage,
            "CAM_FRONT_RIGHT": pix_types.CalibratedImage,
            "CAM_FRONT_LEFT": pix_types.CalibratedImage,
            "CAM_BACK": pix_types.CalibratedImage,
            "CAM_BACK_RIGHT": pix_types.CalibratedImage,
            "CAM_BACK_LEFT": pix_types.CalibratedImage,
            "LIDAR_TOP": pix_types.CalibratedPointCloud,
        },
        bbox3d=pix_types.BBox3D,
    )

    try:
        # Remove the directory and all its contents
        shutil.rmtree(target_dir)
        print(f"Directory '{target_dir}' has been removed.")
    except Exception as e:
        print(f"Error: {e}")

    tri3d_dataset = NuScenes("/home/mfauvel/Documents/Roucky/users/nuscenes", "v1.0-mini")
    builder = Dataset3DBuilder(target_dir=target_dir, dataset_info=info, tri3d_dataset=tri3d_dataset)
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


test_3d_dataset_builder()
