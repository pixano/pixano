# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""3D folder builders (tri3d-based).

The v1 media folder builders were removed in 0.8 in favor of the io import
pipeline; only the tri3d 3D builder remains here.
"""

from .builder_3d import Dataset3DBuilder


__all__ = [
    "Dataset3DBuilder",
]
