# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any, Literal

import numpy as np
from lancedb.pydantic import Vector
from pydantic import model_validator
from typing_extensions import Self

from pixano.features.utils import boxes as bbox_utils
from pixano.utils import issubclass_strict

from ..views import CalibratedImage
from .compressed_rle import CompressedRLE
from .per_frame_annotation import PerFrameAnnotation


class BBox(PerFrameAnnotation):
    """Bounding box using coordinates in xyxy or xywh format.

    Attributes:
        coords: List of coordinates in given format.
        format: Coordinates format, 'xyxy' or 'xywh'.
        is_normalized: True if coordinates are normalized to image size.
        confidence: Bounding box confidence if predicted. -1 if not predicted.
    """

    coords: list[float]
    format: str
    is_normalized: bool
    confidence: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if len(self.coords) != 4:
            raise ValueError("Bounding box coordinates must have 4 elements.")
        elif not all(coord >= 0 for coord in self.coords):
            raise ValueError("Bounding box coordinates must be positive.")
        elif self.is_normalized and not all(0 <= coord <= 1 for coord in self.coords):
            raise ValueError("Normalized bounding box coordinates must be in [0, 1] range.")
        elif (self.confidence < 0 or self.confidence > 1) and not self.confidence == -1:
            raise ValueError("Bounding box confidence must be in [0, 1] range or -1.")
        elif self.format not in ["xyxy", "xywh"]:
            raise ValueError("Bounding box format must be 'xyxy' or 'xywh'.")
        return self

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" `BBox`.
        """
        return cls(
            id="",
            coords=[0.0, 0.0, 0.0, 0.0],
            format="xywh",
            is_normalized=True,
            confidence=-1,
        )

    @property
    def xyxy_coords(self) -> list[float]:
        """Return the bounding box xyxy coordinates.

        Returns:
            Coordinates in xyxy format.
        """
        return self.coords if self.format == "xyxy" else bbox_utils.xywh_to_xyxy(self.coords)

    @property
    def xywh_coords(self) -> list[float]:
        """Return the bounding box xywh coordinates.

        Returns:
            Coordinates in xywh format.
        """
        return self.coords if self.format == "xywh" else bbox_utils.xyxy_to_xywh(self.coords)

    def to_xyxy(self) -> Self:
        """Return the bounding box in xyxy format.

        Returns:
            Bounding box in xyxy format.
        """
        return BBox(
            coords=self.xyxy_coords,
            format="xyxy",
            is_normalized=self.is_normalized,
            confidence=self.confidence,
        )

    def to_xywh(self) -> Self:
        """Return the bounding box in xywh format.

        Returns:
            Bounding box in xyxy format.
        """
        return BBox(
            coords=self.xywh_coords,
            format="xywh",
            is_normalized=self.is_normalized,
            confidence=self.confidence,
        )

    def normalize(self, height: int, width: int) -> Self:
        """Return the bounding box with coordinates normalized relatively to the image size.

        Args:
            height: Image height.
            width: Image width.

        Returns:
            Bounding box with coordinates normalized relatively to the image size.
        """
        return BBox(
            coords=bbox_utils.normalize_coords(self.coords, height, width),
            format=self.format,
            is_normalized=True,
            confidence=self.confidence,
        )

    def denormalize(self, height: int, width: int) -> Self:
        """Return the bounding box with coordinates denormalized relatively to the image size.

        Args:
            height: Image height.
            width: Image width.

        Returns:
            Bounding box with coordinates denormalized relatively to the image size.
        """
        return BBox(
            coords=bbox_utils.denormalize_coords(self.coords, height, width),
            format=self.format,
            is_normalized=False,
            confidence=self.confidence,
        )

    @staticmethod
    def from_xyxy(
        xyxy: list[float],
        **kwargs: Any,
    ) -> "BBox":
        """Create a bounding box using normalized xyxy coordinates.

        Args:
            xyxy: List of coordinates in xyxy format.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox(
            coords=xyxy,
            format="xyxy",
            **kwargs,
        )

    @staticmethod
    def from_xywh(
        xywh: list[float],
        **kwargs: Any,
    ) -> "BBox":
        """Create a bounding box using normalized xywh coordinates.

        Args:
            xywh: List of coordinates in xywh format.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox(
            coords=xywh,
            format="xywh",
            **kwargs,
        )

    @staticmethod
    def from_mask(mask: np.ndarray, **kwargs: Any) -> "BBox":
        """Create a bounding box using a NumPy array mask.

        Args:
            mask: NumPy array mask.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox.from_xywh(
            xywh=bbox_utils.mask_to_bbox(mask),
            is_normalized=True,
            **kwargs,
        )

    @staticmethod
    def from_rle(
        rle: CompressedRLE,
        **kwargs: Any,
    ) -> "BBox":
        """Create a bounding box using a RLE mask.

        Args:
            rle: RLE mask.
            kwargs: Additional arguments.

        Returns:
            The bounding box.
        """
        return BBox.from_mask(mask=rle.to_mask(), **kwargs)


class BBox3D(PerFrameAnnotation):
    """A 3D bounding box.

    Attributes:
        coords: List of 6 coordinates in given format.
        format: Coordinates format, 'xyzxyz' or 'xyzwhd'.
        rotation: Orientation as a row-major flattened 3×3 rotation matrix (9 elements).
        is_normalized: True if coordinates are normalized.
        confidence: Bounding box confidence if predicted. -1 if not predicted.
    """

    coords: Vector(6)  # type: ignore[valid-type]
    format: str
    rotation: Vector(9)  # type: ignore[valid-type]
    is_normalized: bool
    confidence: float = -1.0

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if len(self.coords) != 6:
            raise ValueError("3D bounding box coordinates must have 6 elements.")
        elif self.is_normalized and not all(0 <= coord <= 1 for coord in self.coords):
            raise ValueError("Normalized bounding box coordinates must be in [0, 1] range.")
        elif (self.confidence < 0 or self.confidence > 1) and self.confidence != -1:
            raise ValueError("Bounding box confidence must be in [0, 1] range or -1.")
        elif self.format not in ["xyzxyz", "xyzwhd"]:
            raise ValueError("Bounding box format must be 'xyzxyz' or 'xyzwhd'.")
        elif len(self.rotation) != 9:
            raise ValueError("Rotation matrix must have 9 elements (row-major flattened 3×3).")
        return self

    @classmethod
    def none(cls) -> Self:
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" BBox3D.
        """
        return cls(
            id="",
            coords=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            format="xyzwhd",
            rotation=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            is_normalized=False,
            confidence=-1,
        )

    def get_3dbbox_corners(self) -> np.ndarray:
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
        center = self.coords[:3]
        size = self.coords[3:]

        rotation_mat = np.zeros((3, 3))
        rotation_mat[0] = self.rotation[:3]
        rotation_mat[1] = self.rotation[3:6]
        rotation_mat[2] = self.rotation[6:]

        # Scale the unit cube corners by the size and translate them to the center of the bounding box
        scaled_corners = unit_cube_corners * size
        rotated_corners = (rotation_mat @ scaled_corners.T).T
        translated_corners = rotated_corners + center
        return translated_corners

    def get_bbox2d_coords(self, calibrated_image: CalibratedImage) -> list[float]:
        """Get the 2D bounding box coordinates corresponding to the 3D bounding box for a given camera.
        return [] if the 3D bounding box is not visible in the camera view.

        Args:
            calibrated_image: The calibrated image of the camera.
        """
        projected_corners = project_points(
            self.get_3dbbox_corners(),
            calibrated_image.f,
            calibrated_image.c,
            extrinsics=np.array(calibrated_image.extrinsic_matrix).reshape(4, 4),
        )

        if np.any(projected_corners[:, 2] < 0):
            return []

        minx, maxx = np.min(projected_corners[:, 0]), np.max(projected_corners[:, 0])
        miny, maxy = np.min(projected_corners[:, 1]), np.max(projected_corners[:, 1])

        if minx > calibrated_image.width or maxx < 0 or miny > calibrated_image.height or maxy < 0:
            return []

        minx, maxx = np.clip([minx, maxx], 0, calibrated_image.width)
        miny, maxy = np.clip([miny, maxy], 0, calibrated_image.height)
        sizex, sizey = maxx - minx, maxy - miny
        return [minx, miny, sizex, sizey]


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


def is_bbox(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `BBox` or a subclass of `BBox`."""
    return issubclass_strict(cls, BBox, strict)


def is_bbox3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `BBox3D` or subclass of `BBox3D`."""
    return issubclass_strict(cls, BBox3D, strict)


def create_bbox(
    coords: list[float],
    format: Literal["xyxy", "xywh"],
    is_normalized: bool,
    confidence: float = -1,
    id: str = "",
    record_id: str = "",
    view_id: str = "",
    entity_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
    tracklet_id: str = "",
    entity_dynamic_state_id: str = "",
    frame_id: str = "",
    frame_index: int = -1,
) -> BBox:
    """Create a `BBox` instance.

    Args:
        coords: List of coordinates in given format.
        format: Coordinates format, 'xyxy' or 'xywh'.
        is_normalized: True if coordinates are normalized to image size.
        confidence: Bounding box confidence if predicted.
        id: BBox ID.
        record_id: Record ID.
        view_id: View ID.
        entity_id: Entity ID.
        source_type: Source type.
        source_name: Source name.
        source_metadata: Source metadata (JSON string).
        tracklet_id: Tracklet ID.
        entity_dynamic_state_id: Entity dynamic state ID.
        frame_id: Frame/view row ID.
        frame_index: Frame index.

    Returns:
        The created `BBox` instance.
    """
    return BBox(
        id=id,
        record_id=record_id,
        view_id=view_id,
        entity_id=entity_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
        tracklet_id=tracklet_id,
        entity_dynamic_state_id=entity_dynamic_state_id,
        frame_id=frame_id,
        frame_index=frame_index,
        coords=coords,
        format=str(format),
        is_normalized=is_normalized,
        confidence=confidence,
    )


def create_bbox3d(
    coords: list[float],
    format: Literal["xyzxyz", "xyzwhd"],
    rotation: list[float],
    is_normalized: bool,
    confidence: float = -1.0,
    id: str = "",
    record_id: str = "",
    view_id: str = "",
    entity_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
    tracklet_id: str = "",
    entity_dynamic_state_id: str = "",
    frame_id: str = "",
    frame_index: int = -1,
) -> BBox3D:
    """Create a `BBox3D` instance.

    Args:
        coords: The 3D position coordinates (6 elements).
        format: Coordinates format, 'xyzxyz' or 'xyzwhd'.
        rotation: Row-major flattened 3×3 rotation matrix (9 elements).
        is_normalized: True if coordinates are normalized.
        confidence: Bounding box confidence if predicted.
        id: BBox3D ID.
        record_id: Record ID.
        view_id: View ID.
        entity_id: Entity ID.
        source_type: Source type.
        source_name: Source name.
        source_metadata: Source metadata (JSON string).
        tracklet_id: Tracklet ID.
        entity_dynamic_state_id: Entity dynamic state ID.
        frame_id: Frame/view row ID.
        frame_index: Frame index.

    Returns:
        The created `BBox3D` instance.
    """
    return BBox3D(
        id=id,
        record_id=record_id,
        view_id=view_id,
        entity_id=entity_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
        tracklet_id=tracklet_id,
        entity_dynamic_state_id=entity_dynamic_state_id,
        frame_id=frame_id,
        frame_index=frame_index,
        coords=coords,
        format=format,
        rotation=rotation,
        is_normalized=is_normalized,
        confidence=confidence,
    )
