# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.utils.video import create_video_preview


@pytest.mark.skip("Not implemented")
def test_create_video_preview():
    try:
        import mediapy
    except ImportError:
        pytest.skip("mediapy not installed")
