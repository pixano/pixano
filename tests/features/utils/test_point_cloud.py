# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests for the point-cloud BEV preview generator."""

import io

import numpy as np
from PIL import Image

from pixano.features.utils.point_cloud import PREVIEW_SIZE, generate_bev_preview


def _decode(preview: bytes) -> Image.Image:
    return Image.open(io.BytesIO(preview))


class TestGenerateBevPreview:
    def test_returns_png_of_requested_size(self):
        rng = np.random.default_rng(0)
        points = rng.uniform(-10, 10, size=(2000, 4)).astype(np.float32)  # x,y,z,intensity
        preview = generate_bev_preview(points, size=32)
        assert preview is not None
        img = _decode(preview)
        assert img.format == "PNG"
        assert img.size == (32, 32)

    def test_default_size(self):
        points = np.random.default_rng(1).uniform(-5, 5, size=(500, 3))
        img = _decode(generate_bev_preview(points))
        assert img.size == (PREVIEW_SIZE, PREVIEW_SIZE)

    def test_renders_some_non_background_pixels(self):
        # A diagonal line of points should light up cells (not an all-black image).
        t = np.linspace(-10, 10, 400)
        points = np.stack([t, t, t], axis=1)
        arr = np.asarray(_decode(generate_bev_preview(points)))
        assert arr.max() > 0  # at least some colored cells

    def test_is_deterministic(self):
        points = np.random.default_rng(2).uniform(-8, 8, size=(1000, 3))
        assert generate_bev_preview(points) == generate_bev_preview(points)

    def test_empty_returns_none(self):
        assert generate_bev_preview(np.empty((0, 3))) is None

    def test_too_few_columns_returns_none(self):
        assert generate_bev_preview(np.zeros((10, 2))) is None

    def test_degenerate_extent_returns_none(self):
        # All points at the same (x, y) → zero spatial extent.
        points = np.zeros((50, 3))
        assert generate_bev_preview(points) is None

    def test_non_finite_only_returns_none(self):
        points = np.full((10, 3), np.nan)
        assert generate_bev_preview(points) is None

    def test_ignores_non_finite_points(self):
        good = np.random.default_rng(3).uniform(-5, 5, size=(200, 3))
        bad = np.full((5, 3), np.inf)
        preview = generate_bev_preview(np.vstack([good, bad]))
        assert preview is not None
