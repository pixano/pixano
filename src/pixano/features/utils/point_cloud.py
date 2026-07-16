# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Point-cloud preview helpers.

A point cloud cannot be thumbnailed like an image, so we render a top-down
*bird's-eye-view* (BEV) raster: points are projected onto the XY plane, binned
into a small grid, and colored by height. The result is a tiny PNG suitable for
the same preview pipeline images use.
"""

import io

import numpy as np
from PIL import Image


#: Side length (px) of the square BEV preview. Matches the image thumbnail size.
PREVIEW_SIZE = 64
#: Output image format (mirrors the image preview).
PREVIEW_FORMAT = "png"
#: Percentiles used to clip spatial/height extents so a few outliers don't
#: collapse the useful range into a single bin.
_CLIP_LOW_PCT = 2.0
_CLIP_HIGH_PCT = 98.0


def _height_colormap(t: np.ndarray) -> np.ndarray:
    """Map normalized heights in ``[0, 1]`` to RGB (blue → green → red)."""
    t = np.clip(t, 0.0, 1.0)
    r = np.clip((t - 0.5) * 2.0, 0.0, 1.0)
    b = np.clip((0.5 - t) * 2.0, 0.0, 1.0)
    g = np.clip(1.0 - r - b, 0.0, 1.0)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def generate_bev_preview(points_xyz: np.ndarray, size: int = PREVIEW_SIZE) -> bytes | None:
    """Render a bird's-eye-view PNG thumbnail from point coordinates.

    Args:
        points_xyz: Array of shape (N, >=3); only the first three columns
            (x, y, z) are used.
        size: Side length of the square output in pixels.

    Returns:
        PNG-encoded bytes, or ``None`` when the input has no usable points
        (empty, non-finite, or zero spatial extent) so the caller can leave the
        preview unset.
    """
    pts = np.asarray(points_xyz, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 3:
        return None

    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if not finite.any():
        return None
    x, y, z = x[finite], y[finite], z[finite]

    x_lo, x_hi = np.percentile(x, [_CLIP_LOW_PCT, _CLIP_HIGH_PCT])
    y_lo, y_hi = np.percentile(y, [_CLIP_LOW_PCT, _CLIP_HIGH_PCT])
    if x_hi <= x_lo or y_hi <= y_lo:
        return None

    col = np.clip(((x - x_lo) / (x_hi - x_lo) * (size - 1)).astype(np.int64), 0, size - 1)
    row = np.clip(((y - y_lo) / (y_hi - y_lo) * (size - 1)).astype(np.int64), 0, size - 1)

    # Height (max z) per cell; empty cells stay non-finite so they render as
    # background.
    heights = np.full(size * size, -np.inf)
    np.maximum.at(heights, row * size + col, z)
    filled = np.isfinite(heights)

    pixels = np.zeros((size * size, 3), dtype=np.uint8)  # black background
    if filled.any():
        hv = heights[filled]
        z_lo, z_hi = np.percentile(hv, [_CLIP_LOW_PCT, _CLIP_HIGH_PCT])
        norm = np.full_like(hv, 0.5) if z_hi <= z_lo else np.clip((hv - z_lo) / (z_hi - z_lo), 0.0, 1.0)
        pixels[filled] = _height_colormap(norm)

    # Row 0 is the top of the image; flip so +y points up (natural BEV).
    raster = np.flipud(pixels.reshape(size, size, 3))
    out = io.BytesIO()
    Image.fromarray(raster, mode="RGB").save(out, format=PREVIEW_FORMAT.upper())
    return out.getvalue()
