# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import collections
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterator
from unicodedata import name

import lancedb
import numpy as np
from lancedb.pydantic import LanceModel
from PIL import Image
from pydantic import ConfigDict, model_validator
from tri3d import quaternion

# from scipy.spatial.transform import Rotation as R
from tri3d.datasets import Dataset as Tri3dDataset
from tri3d.datasets import NuScenes
from tri3d.geometry import test_box_in_frame

import pixano.features as pix_types
from pixano.datasets import Dataset, DatasetInfo, dataset
from pixano.datasets.builders import DatasetBuilder
from pixano.features import NDArrayFloat, SequenceFrame
from pixano.schemas.annotations import BBox, BBox3D


# from pixano.features.types.schema_reference import ItemRef, ViewRef


class Dataset3DBuilder(DatasetBuilder):
    """Dataset builder for 3D datasets supported by tri3d."""

    def __init__(self,target_dir: Path | str, dataset_info: DatasetInfo, tri3d_dataset:Tri3dDataset):
        super().__init__(target_dir, dataset_info)
        self.tri3d_dataset = tri3d_dataset

    def generate_data(self) -> Iterator[Dict[str, LanceModel | list[LanceModel]]]:
        """Generate data for the dataset.

        Yields:
            An iterator of dictionaries mapping table names to lists of LanceModel instances.
        """
        for i in self.tri3d_dataset.sequences():
            # just cameras for now, but we could add lidar and radar too
            cam_sensors = self.tri3d_dataset.cam_sensors
            for sensor in cam_sensors:
                for j in self.tri3d_dataset.frames(i, sensor):
                    yield self._generate_record(i, j, sensor)

        print("ouais")


    def _generate_record(self, seq, frame, sensor: str):
        """Generate a record for a given record ID."""
        # Create record
        res = {}
        res["records"] = []
        record = self.schemas["records"](id=f"record_{seq}_{frame}_{sensor}", split=sensor)
        res["records"].append(record)
        # Add calibrated sequence frame view
        res["sequence_frames"] = []

        # Calibrations

        # calib=self.tri3d_dataset._calibration(seq, frame, sensor)
        # intrinsics = (calib.intrinsics[0],calib.intrinsics[1],calib.intrinsics[2],calib.intrinsics[3],0,0,0,0,0,0,0)
        intrincs = (
            self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][0][0],
            self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][1][1],
            self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][0][2],
            self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][1][2],
            0, 0, 0, 0, 0
        )
        # Extrinsics
        extrinsic = self.get_transformation_matrix(seq, sensor, frame)

        #Ego to world
        # ego2world = self.get_transformation_matrix(seq, "ego", frame)

        sequence_frame = pix_types.CalibratedSequenceFrame.from_uri(
            record_id=record.id,
            logical_name=f"calibrated_sequence_frame_{seq}_{frame}_{sensor}",
            uri="/home/mfauvel/Datasets/NuScenes/" + str(self.tri3d_dataset.scenes[seq].data[sensor][frame]),
            intrinsics=intrincs,
            extrinsic_matrix=extrinsic.tolist(),
            ego_to_world=extrinsic.tolist(),
            frame_index=frame
        )
        res["sequence_frames"].append(sequence_frame)

        return res
    def get_transformation_matrix(self, seq: int, sensor: str, frame: int) -> np.ndarray:
        """Get the transformation matrix for a given sequence and sensor."""
        R = self.tri3d_dataset.poses(seq, sensor)[frame].rotation.mat
        C = self.tri3d_dataset.poses(seq, sensor)[frame].translation.vec
        # translation
        t = -R @ C
        # matrix 4x4
        matrix = np.eye(4)
        matrix[:3, :3] = R
        matrix[:3, 3] = t
        return matrix

def main():
    name="Nuscenes tri3d"
    source_dir = "/home/mfauvel/Datasets/NuScenes/v1.0-mini"
    target_dir = f"/home/mfauvel/Documents/pixano_data/library/{name}"
    info = DatasetInfo(
        name=name,
        description="Nuscenes built with tri3d",
        record=pix_types.Record
    )

    try:
        # Remove the directory and all its contents
        shutil.rmtree(target_dir)
        print(f"Directory '{target_dir}' has been removed.")
    except Exception as e:
        print(f"Error: {e}")

    tri3d_dataset = NuScenes("/home/mfauvel/Datasets/NuScenes", "v1.0-mini")
    builder = Dataset3DBuilder(target_dir=target_dir, dataset_info=info, tri3d_dataset=tri3d_dataset)
    builder.build()

    db = lancedb.connect(Path(target_dir) / "db")
    print("---------------")
    print("All tables :", ", ".join(db.list_tables()))
    print("---------------")

    for tname in db.table_names():
        df = db.open_table(tname).to_pandas()
        print("---------------", tname, ",", len(df), "samples", "---------------------")
        print(df.info(verbose=False))
        print(df)

main()
