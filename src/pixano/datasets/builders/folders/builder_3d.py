# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
from pathlib import Path
from typing import Dict, Iterator

import numpy as np
from lancedb.pydantic import LanceModel
from tri3d.datasets import Dataset as Tri3dDataset

import pixano.features as pix_types
from pixano.datasets import DatasetInfo
from pixano.datasets.builders import DatasetBuilder
from pixano.features.utils.point_cloud import PREVIEW_FORMAT, generate_bev_preview


logger = logging.getLogger(__name__)


class CategoryEntity(pix_types.Entity):
    """Entity with a category."""

    category: str


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
            bbox=pix_types.BBox,
            entity=CategoryEntity,
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

        ids = 1
        for i in self.tri3d_dataset.sequences():
            idx = 1
            for j in self.tri3d_dataset.frames(i, ego_sensor):
                yield from self._generate_record(i, j, ego_sensor)
                if idx == 4:
                    break
                idx += 1
            if ids == 3:
                break
            ids += 1

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
                self.tri3d_dataset._calibration(
                    seq, ego_sensor, self.tri3d_dataset.img_sensors[self.tri3d_dataset.cam_sensors.index(sensor)]
                )
                .operations[1]
                .intrinsics[0],
                self.tri3d_dataset._calibration(
                    seq, ego_sensor, self.tri3d_dataset.img_sensors[self.tri3d_dataset.cam_sensors.index(sensor)]
                )
                .operations[1]
                .intrinsics[1],
            )
            c = (
                self.tri3d_dataset._calibration(
                    seq, ego_sensor, self.tri3d_dataset.img_sensors[self.tri3d_dataset.cam_sensors.index(sensor)]
                )
                .operations[1]
                .intrinsics[2],
                self.tri3d_dataset._calibration(
                    seq, ego_sensor, self.tri3d_dataset.img_sensors[self.tri3d_dataset.cam_sensors.index(sensor)]
                )
                .operations[1]
                .intrinsics[3],
            )
            distortion = (
                self.tri3d_dataset._calibration(
                    seq, ego_sensor, self.tri3d_dataset.img_sensors[self.tri3d_dataset.cam_sensors.index(sensor)]
                )
                .operations[1]
                .intrinsics[3:]
            )

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
            sensor2world = self.tri3d_dataset.poses(seq, sensor)[frame]
            world_points = sensor2world.apply(self.tri3d_dataset.points(seq, frame, sensor)[:, :3])
            points = np.hstack((world_points, self.tri3d_dataset.points(seq, frame, sensor)[:, 3:]), dtype=np.float32)
            raw_bytes = points.tobytes()
            # A preview is a best-effort thumbnail; never let it abort an import.
            try:
                preview = generate_bev_preview(points[:, :3])
            except Exception:
                logger.warning(
                    "Failed to generate BEV preview for point cloud %s_%s_%s", sensor, seq, frame, exc_info=True
                )
                preview = None
            pcd = self.info.views[sensor](
                record_id=record.id,
                logical_name=sensor,
                raw_bytes=raw_bytes,
                preview=preview or b"",
                preview_format=PREVIEW_FORMAT if preview else "",
                id=f"{sensor}_{seq}_{frame}",
                extrinsic_matrix=self.get_transformation_matrix(seq, sensor, frame),
                ego_to_world=self.get_transformation_matrix(seq, ego_sensor, frame),
            )
            res["point_clouds"].append(pcd)

        # add 3D bounding boxes and 2D bounding boxes from the 3D boxes and associate them to an entity
        res["entities"] = []
        res["bbox3ds"] = []
        res["bboxes"] = []
        for id, ann in enumerate(self.tri3d_dataset.boxes(seq, frame, coords=ego_sensor)):
            # create entity for bbox
            entity = self.schemas["entities"](
                id=f"entity_{seq}_{frame}_{id}",
                record_id=record.id,
                logical_name="entity",
                category=ann.label,
            )
            res["entities"].append(entity)

            # creation of the 3D bbox in world coordinates
            sensor2world = self.tri3d_dataset.poses(seq, ego_sensor)[frame]
            z_angle_world = np.arctan2(sensor2world.rotation.mat[1, 0], sensor2world.rotation.mat[0, 0])
            rotation = [
                np.cos(ann.heading + z_angle_world),
                -np.sin(ann.heading + z_angle_world),
                0,
                np.sin(ann.heading + z_angle_world),
                np.cos(ann.heading + z_angle_world),
                0,
                0,
                0,
                1,
            ]
            world_center = sensor2world.apply(ann.center)
            bbox3d = self.schemas["bbox3ds"](
                coords=[world_center[0], world_center[1], world_center[2], ann.size[0], ann.size[1], ann.size[2]],
                format="xyzwhd",
                rotation=rotation,
                is_normalized=False,
                record_id=record.id,
                logical_name="bbox3d",
                entity_id=entity.id,
                id=f"bbox3d_{seq}_{frame}_{id}",
            )
            res["bbox3ds"].append(bbox3d)

            # creation of the 2D bbox
            for image in res["calibrated_images"]:
                coords = bbox3d.get_bbox2d_coords(image)
                if coords == []:
                    continue

                bbox2d = self.schemas["bboxes"](
                    coords=coords,
                    format="xywh",
                    is_normalized=False,
                    record_id=record.id,
                    logical_name="bbox2d",
                    entity_id=entity.id,
                    id=f"bbox2d_{seq}_{frame}_{id}_{image.logical_name}",
                    view_id=image.id,
                )
                res["bboxes"].append(bbox2d)

        yield res

    def get_transformation_matrix(self, seq: int, sensor: str, frame: int) -> np.ndarray:
        """Get the transformation matrix for a given sequence and sensor."""
        R = self.tri3d_dataset.poses(seq, sensor)[frame].rotation.mat.T
        C = self.tri3d_dataset.poses(seq, sensor)[frame].translation.vec
        # translation
        t = -R @ C
        # matrix 4x4
        matrix = np.eye(4)
        matrix[:3, :3] = R
        matrix[:3, 3] = t
        return matrix.flatten().tolist()
