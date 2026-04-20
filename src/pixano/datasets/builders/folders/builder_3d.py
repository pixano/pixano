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

import pixano.features as pix_types
from pixano.datasets import DatasetInfo
from pixano.datasets.builders import DatasetBuilder


class Dataset3DBuilder(DatasetBuilder):
    """Dataset builder for 3D datasets supported by tri3d."""

    def __init__(
        self,
        target_dir: Path | str,
        source_dir: str,
        dataset_name: str,
        dataset_description: str,
        tri3d_dataset: Tri3dDataset,
    ):
        """Initialize the 3D dataset builder for datasets supported by tri3d.

        Args:
            target_dir (Path | str): The target directory for the dataset.
            source_dir (Path | str): The source directory for the dataset.
            dataset_name (str): The name of the dataset.
            dataset_description (str): The description of the dataset.
            tri3d_dataset (Tri3dDataset): The tri3d dataset to build.
        """
        info = DatasetInfo(
            name=dataset_name,
            description=dataset_description,
            record=pix_types.Record,
            views={
                **{f"{sensor}": pix_types.CalibratedImage for sensor in tri3d_dataset.cam_sensors},
                **{f"{sensor}": pix_types.CalibratedPointCloud for sensor in tri3d_dataset.pcl_sensors},
            },
            bbox3d=pix_types.BBox3D,
        )
        super().__init__(target_dir, info)
        self.tri3d_dataset = tri3d_dataset
        self.source_dir = source_dir

    def generate_data(self) -> Iterator[Dict[str, LanceModel | list[LanceModel]]]:
        """Generate data for the dataset.

        Yields:
            An iterator of dictionaries mapping table names to lists of LanceModel instances.
        """
        ego_sensor = (
            "LIDAR_TOP"  # TODO This only works with nuscenes, should be given as argument or inferred from the
        )
        # dataset

        for i in self.tri3d_dataset.sequences():
            for j in self.tri3d_dataset.frames(i, ego_sensor):
                yield from self._generate_record(i, j, ego_sensor)

    def _generate_record(self, seq, frame, ego_sensor: str):
        """Generate a record for a given record ID."""
        # Create record
        res = {}  # type: Dict[str, list[LanceModel]]
        res["records"] = []
        record = self.schemas["records"](
            id=f"record_{seq}_{frame}", split=self.tri3d_dataset.scenes[seq].data[ego_sensor][frame].split("/")[0]
        )
        res["records"].append(record)

        # Add calibrated image view
        res["calibrated_images"] = []
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

        # Add point cloud view
        res["point_clouds"] = []
        for sensor in self.tri3d_dataset.pcl_sensors:
            filename = self.tri3d_dataset.scenes[seq].data[sensor][frame]
            pcd = self.info.views[sensor](
                record_id=record.id,
                logical_name=sensor,
                uri=self.source_dir + "/" + str(filename),
                id=f"{sensor}_{seq}_{frame}",
                extrinsic_matrix=self.get_transformation_matrix(seq, sensor, frame),
                ego_to_world=self.get_transformation_matrix(seq, ego_sensor, frame),
            )
            res["point_clouds"].append(pcd)

        # add 3D bounding boxes
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
                coords=[-ann.center[1], ann.center[0], ann.center[2], ann.size[0], ann.size[1], ann.size[2]],
                # TODO these coordonates only work for nuscsenes
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
