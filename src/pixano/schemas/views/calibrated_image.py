# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import io
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import PIL.Image
import shortuuid

from pixano.utils import issubclass_strict

from .image import Image, _generate_preview


class CalibratedImage(Image):
    """Calibrated image view.

    Attributes:
        fx: focal
        fy:
        cx: centre optique,
        cy:
        c1: c1.
        c2: c2.
        c3: c3.
        c4: c4.
        pixel_aspect_ratio: pixel_aspect_ratio.

        extrinsic_matrix: extrinsic_matrix. A 4x4 matrix representing the transformation from the camera frame to the world frame.
                         (R | t)     where R is a 3x3 rotation matrix and t is a 3x1 translation vector.
                         (0 0 0 1)   the last row is [0, 0, 0, 1] for homogeneous coordinates.

        ego_to_world: ego_to_world. A 4x4 matrix representing the transformation from the ego frame to the world frame.
                      in the same format as extrinsic_matrix.
    """


    # Intrinsics
    fx: float
    fy: float
    cx: float
    cy: float
    c1: float
    c2: float
    c3: float
    c4: float
    pixel_aspect_ratio: float
    frame_id : str

    #Extrinsics
    extrinsic_matrix: list[list[float]]

    # Ego pose
    ego_to_world: list[list[float]]


    @classmethod
    def from_uri(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        uri: str,
        intrinsics: dict[str, float],
        extrinsics: list[list[float]],
        ego_to_world: list[list[float]],
        *,
        id: str | None = None,
    ) -> CalibratedImage:
        """Create a ``CalibratedImage`` from a URI (local path or remote URL).

        The file is opened to extract *width*, *height* and *format*, and a
        64 x 64 PNG preview thumbnail is generated automatically.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            uri: Absolute file path or remote ``http(s)`` URL.
            intrinsics: Camera intrinsics.
            extrinsics: Camera extrinsics.
            ego_to_world: Ego-to-world transformation.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``CalibratedImage`` instance.
        """
        if id is None:
            id = shortuuid.uuid()

        parsed = urlparse(uri)
        if parsed.scheme in ("http", "https"):
            data = urlopen(uri).read()  # noqa: S310
            pil_image = PIL.Image.open(io.BytesIO(data))
        else:
            pil_image = PIL.Image.open(Path(uri))

        width = pil_image.width
        height = pil_image.height
        fmt = pil_image.format or ""
        preview = _generate_preview(pil_image)

        return cls(
            id=id,
            record_id=record_id,
            logical_name=logical_name,
            uri=uri,
            width=width,
            height=height,
            format=fmt,
            preview=preview,
            preview_format="png",
            fx=intrinsics["fx"],
            fy=intrinsics["fy"],
            cx=intrinsics["cx"],
            cy=intrinsics["cy"],
            c1=intrinsics["c1"],
            c2=intrinsics["c2"],
            c3=intrinsics["c3"],
            c4=intrinsics["c4"],
            pixel_aspect_ratio=intrinsics["pixel_aspect_ratio"],
            frame_id=intrinsics["frame_id"],
            extrinsics=extrinsics,
            ego_to_world=ego_to_world

        )

    @classmethod
    def from_bytes(  # type: ignore[override]
        cls,
        record_id: str,
        logical_name: str,
        raw_bytes: bytes,
        intrinsics: dict[str, float],
        extrinsics: list[list[float]],
        ego_to_world: list[list[float]],
        *,
        id: str | None = None,
    ) -> CalibratedImage:
        """Create a ``CalibratedImage`` from raw bytes.

        The bytes are decoded to extract *width*, *height* and *format*, and a
        64 x 64 PNG preview thumbnail is generated automatically.

        Args:
            record_id: Record ID that owns this view.
            logical_name: Logical view name (e.g. ``"front_camera"``).
            raw_bytes: Image file content as raw bytes.
            intrinsics: Camera intrinsics.
            extrinsics: Camera extrinsics.
            ego_to_world: Ego-to-world transformation.
            id: Optional explicit ID.  Auto-generated with :func:`shortuuid.uuid`
                when *None*.

        Returns:
            A fully-populated ``CalibratedImage`` instance.
        """
        if id is None:
            id = shortuuid.uuid()

        pil_image = PIL.Image.open(io.BytesIO(raw_bytes))

        width = pil_image.width
        height = pil_image.height
        fmt = pil_image.format or ""
        preview = _generate_preview(pil_image)

        return cls(
            id=id,
            record_id=record_id,
            logical_name=logical_name,
            raw_bytes=raw_bytes,
            width=width,
            height=height,
            format=fmt,
            preview=preview,
            preview_format="png",
            fx=intrinsics["fx"],
            fy=intrinsics["fy"],
            cx=intrinsics["cx"],
            cy=intrinsics["cy"],
            c1=intrinsics["c1"],
            c2=intrinsics["c2"],
            c3=intrinsics["c3"],
            c4=intrinsics["c4"],
            pixel_aspect_ratio=intrinsics["pixel_aspect_ratio"],
            frame_id=intrinsics["frame_id"],
            extrinsics=extrinsics,
            ego_to_world=ego_to_world
        )


def is_calibrated_image(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a subclass of ``CalibratedImage``."""
    return issubclass_strict(cls, CalibratedImage, strict)
