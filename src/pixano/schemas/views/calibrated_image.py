# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import PIL.Image
from lancedb.pydantic import Vector

from pixano.schemas.views.image import Image
from pixano.utils import issubclass_strict


class CalibratedImage(Image):
    """Calibrated image view.

    Attributes:
        f: focal coordinates
        c: optical center coordinates
        distortion: distortion coefficients.,

        extrinsic_matrix: A 4x4 matrix representing the transformation from the camera frame to the world frame.
                         (R | t)     where R is a 3x3 rotation matrix and t is a 3x1 translation vector.
                         (0 0 0 1)   the last row is [0, 0, 0, 1] for homogeneous coordinates.

        ego_to_world: A 4x4 matrix representing the transformation from the ego frame to the world frame.
                      in the same format as extrinsic_matrix.
    """

    # Intrinsics
    f: tuple[float, float]
    c: tuple[float, float]
    distortion: list[float]

    # Extrinsics
    extrinsic_matrix: Vector(16)  # type: ignore[valid-type]

    # Ego pose
    ego_to_world: Vector(16)  # type: ignore[valid-type]

    @classmethod
    def from_uri(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        uri: str,
        f: tuple[float, float],
        c: tuple[float, float],
        distortion: list[float],
        extrinsic_matrix: Vector(16),  # type: ignore[valid-type]
        ego_to_world: Vector(16),  # type: ignore[valid-type]
        *,
        id: str | None = None,
    ) -> CalibratedImage:
        """Create a ``CalibratedImage`` from a URI (local path or remote URL).

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            uri: Absolute file path or remote ``http(s)`` URL.
            f: focal coordinates
            c: optical center coordinates
            distortion: distortion coefficients.
            extrinsic_matrix: Camera extrinsics.
            ego_to_world: Ego-to-world transformation.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``CalibratedImage`` instance.
        """
        # Use Image.from_uri() to extract width, height, format, and preview
        image_dict = Image.from_uri(record_id=record_id, logical_name=logical_name, uri=uri, id=id).model_dump()

        return cls(
            **image_dict,
            f=f,
            c=c,
            distortion=distortion,
            extrinsic_matrix=extrinsic_matrix,
            ego_to_world=ego_to_world,
        )

    @classmethod
    def from_bytes(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        raw_bytes: bytes,
        f: tuple[float, float],
        c: tuple[float, float],
        distortion: list[float],
        extrinsic_matrix: Vector(16),  # type: ignore[valid-type]
        ego_to_world: Vector(16),  # type: ignore[valid-type]
        *,
        id: str | None = None,
    ) -> CalibratedImage:
        """Create a ``CalibratedImage`` from raw bytes.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            raw_bytes: Image file content as raw bytes.
            f: focal coordinates
            c: optical center coordinates
            distortion: distortion coefficients.
            extrinsic_matrix: Camera extrinsics.
            ego_to_world: Ego-to-world transformation.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``CalibratedImage`` instance.
        """
        # Use Image.from_bytes() to extract width, height, format, and preview
        image_dict = Image.from_bytes(
            record_id=record_id, logical_name=logical_name, raw_bytes=raw_bytes, id=id
        ).model_dump()

        return cls(
            **image_dict,
            f=f,
            c=c,
            distortion=distortion,
            extrinsic_matrix=extrinsic_matrix,
            ego_to_world=ego_to_world,
        )

    @classmethod
    def from_pil(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        pil_image: PIL.Image,
        f: tuple[float, float],
        c: tuple[float, float],
        distortion: list[float],
        extrinsic_matrix: Vector(16),  # type: ignore[valid-type]
        ego_to_world: Vector(16),  # type: ignore[valid-type]
        *,
        id: str | None = None,
    ) -> CalibratedImage:
        """Create a ``CalibratedImage`` from raw bytes.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            pil_image: A PIL Image instance.
            f: focal coordinates
            c: optical center coordinates
            distortion: distortion coefficients.
            extrinsic_matrix: Camera extrinsics.
            ego_to_world: Ego-to-world transformation.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``CalibratedImage`` instance.
        """
        # Use Image.from_pil() to extract width, height, format, and preview
        image_dict = Image.from_pil(
            record_id=record_id, logical_name=logical_name, pil_image=pil_image, id=id
        ).model_dump()

        return cls(
            **image_dict,
            f=f,
            c=c,
            distortion=distortion,
            extrinsic_matrix=extrinsic_matrix,
            ego_to_world=ego_to_world,
        )


def is_calibrated_image(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of ``CalibratedImage``."""
    return issubclass_strict(cls, CalibratedImage, strict)
