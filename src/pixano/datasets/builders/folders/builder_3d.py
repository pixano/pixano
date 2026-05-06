# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Dict, Iterator

import numpy as np
from lancedb.pydantic import LanceModel
from tri3d.datasets import Dataset as Tri3dDataset

import pixano.features as pix_types
from pixano.datasets import DatasetInfo
from pixano.datasets.builders import DatasetBuilder


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
            pcd = self.info.views[sensor](
                record_id=record.id,
                logical_name=sensor,
                raw_bytes=raw_bytes,
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
            corners_3d = get_3dbbox_corners(bbox3d)
            for image in res["calibrated_images"]:
                extrinsics = np.array(image.extrinsic_matrix).reshape(4, 4)
                projected_corners = project_points(corners_3d, image.f, image.c, extrinsics)
                if np.any(projected_corners[:, 2] < 0):
                    continue

                minx, maxx = np.min(projected_corners[:, 0]), np.max(projected_corners[:, 0])
                miny, maxy = np.min(projected_corners[:, 1]), np.max(projected_corners[:, 1])

                if minx > image.width or maxx < 0 or miny > image.height or maxy < 0:
                    continue

                minx, maxx = np.clip([minx, maxx], 0, image.width)
                miny, maxy = np.clip([miny, maxy], 0, image.height)

                center = [(minx + maxx) / 2, (miny + maxy) / 2]
                size = [maxx - minx, maxy - miny]
                bbox2d = self.schemas["bboxes"](
                    coords=[center[0], center[1], size[0], size[1]],
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


def get_3dbbox_corners(bbox: pix_types.BBox3D) -> np.ndarray:
    """Get the corners of a 3D bounding box."""
    # Define the corners of a unit cube centered at the origin
    unit_cube_corners = np.array(
        [
            [-0.5, -0.5, -0.5],
            [0.5, -0.5, -0.5],
            [0.5, 0.5, -0.5],
            [-0.5, 0.5, -0.5],
            [-0.5, -0.5, 0.5],
            [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5],
            [-0.5, 0.5, 0.5],
        ]
    )
    center = bbox.coords[:3]
    size = bbox.coords[3:]

    rotation_mat = np.zeros((3, 3))
    rotation_mat[0] = bbox.rotation[:3]
    rotation_mat[1] = bbox.rotation[3:6]
    rotation_mat[2] = bbox.rotation[6:]

    # Scale the unit cube corners by the size and translate them to the center of the bounding box
    scaled_corners = unit_cube_corners * size
    rotated_corners = (rotation_mat @ scaled_corners.T).T
    translated_corners = rotated_corners + center
    return translated_corners


def project_points(points_3d, f, c, extrinsics):
    """Projects 3D points onto a 2D image plane.

     points_3d: (N, 3)
    f: focale (fx, fy)
    c: centre (cx, cy)
    extrinsics: extrinsic matrix (4x4)
    """
    N = len(points_3d)

    # homogeneous coordinates (N, 4)
    points_h = np.hstack((points_3d, np.ones((N, 1))))

    # world -> camera; keep x,y,z
    points_cam = (extrinsics @ points_h.T).T[:, :3]
    points_cam[:, 0] = np.sign(points_cam[:, 2]) * points_cam[:, 0] / points_cam[:, 2]
    points_cam[:, 1] = np.sign(points_cam[:, 2]) * points_cam[:, 1] / points_cam[:, 2]
    # 3D -> 2D
    u = f[0] * points_cam[:, 0] + c[0]
    v = f[1] * points_cam[:, 1] + c[1]

    return np.stack([u, v, points_cam[:, 2]], axis=-1)
