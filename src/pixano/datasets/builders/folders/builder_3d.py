# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

# %%
from pathlib import Path
from typing import Dict, Iterator

import numpy as np
from lancedb.pydantic import LanceModel
from tri3d.datasets import Dataset as Tri3dDataset

from pixano.datasets import DatasetInfo
from pixano.datasets.builders import DatasetBuilder


class Dataset3DBuilder(DatasetBuilder):
    """Dataset builder for 3D datasets supported by tri3d."""

    def __init__(self, target_dir: Path | str, dataset_info: DatasetInfo, tri3d_dataset: Tri3dDataset):
        """Initialize the 3D dataset builder for datasets supported by tri3d.

        Args:
            target_dir (Path | str): The target directory for the dataset.
            dataset_info (DatasetInfo): Dataset information including table→schema mapping.
            tri3d_dataset (Tri3dDataset): The tri3d dataset to build.
        """
        super().__init__(target_dir, dataset_info)
        self.tri3d_dataset = tri3d_dataset

    def generate_data(self) -> Iterator[Dict[str, LanceModel | list[LanceModel]]]:
        """Generate data for the dataset.

        Yields:
            An iterator of dictionaries mapping table names to lists of LanceModel instances.
        """
        idx = 1
        for i in self.tri3d_dataset.sequences():
            ego_sensor = "LIDAR_TOP"
            for j in self.tri3d_dataset.frames(i, ego_sensor):
                yield from self._generate_record(i, j, ego_sensor)
                if idx == 4:
                    break
                idx += 1
            if idx == 4:
                break

    def _generate_record(self, seq, frame, ego_sensor: str):
        """Generate a record for a given record ID."""
        # Create record
        res = {}  # type: Dict[str, list[LanceModel]]
        res["records"] = []
        record = self.schemas["records"](
            id=f"record_{seq}_{frame}", split=self.tri3d_dataset.scenes[seq].data[ego_sensor][frame].split("/")[0]
        )  # enlever les sensor (7 view diff)
        res["records"].append(record)

        # Add calibrated image view
        res["calibrated_images"] = []
        # Calibrations
        for sensor in self.tri3d_dataset.cam_sensors:
            f = (
                self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][0][0],
                self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][1][1],
            )
            c = (
                self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][0][2],
                self.tri3d_dataset.scenes[seq].calibration[sensor]["camera_intrinsic"][1][2],
            )
            distortion = [0, 0, 0, 0]

            cam_image = self.info.views[sensor].from_pil(
                record_id=record.id,
                logical_name=sensor,
                pil_image=self.tri3d_dataset.image(seq, frame, sensor),
                id=f"{sensor}_{seq}_{frame}",
                f=f,
                c=c,
                distortion=distortion,
                extrinsic_matrix=self.get_transformation_matrix(seq, sensor, frame),
                ego_to_world=self.get_transformation_matrix(seq, ego_sensor, frame),
            )
            res["calibrated_images"].append(cam_image)

        res["point_clouds"] = []
        for sensor in self.tri3d_dataset.pcl_sensors:
            filename = self.tri3d_dataset.scenes[seq].data[sensor][frame]
            pcd = self.info.views[sensor](
                record_id=record.id,
                logical_name=sensor,
                uri="/home/mfauvel/Documents/Roucky/users/nuscenes/" + str(filename),
                id=f"{sensor}_{seq}_{frame}",
                extrinsic_matrix=self.get_transformation_matrix(seq, sensor, frame),
                ego_to_world=self.get_transformation_matrix(seq, ego_sensor, frame),
            )
            res["point_clouds"].append(pcd)

        res["bbox3ds"] = []
        for id, ann in enumerate(self.tri3d_dataset.boxes(seq, frame, coords=ego_sensor)):
            rotation = [
                np.cos(ann.heading),
                -np.sin(ann.heading),
                0,
                np.sin(ann.heading),
                np.cos(ann.heading),
                0,
                0,
                0,
                1,
            ]
            bbox = self.schemas["bbox3ds"](
                coords=[ann.center[0], ann.center[1], ann.center[2], ann.size[0], ann.size[1], ann.size[2]],
                format="xyzwhd",
                rotation=rotation,
                is_normalized=False,
                record_id=record.id,
                logical_name="bbox3d",
                category=ann.label,
                id=f"bbox3d_{seq}_{frame}_{id}",
            )
            res["bbox3ds"].append(bbox)
        yield res

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
        return matrix.flatten().tolist()
