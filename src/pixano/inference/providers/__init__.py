# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from .base import HTTPProvider
from .pixano_inference import PixanoInferenceProvider


__all__ = [
    "HTTPProvider",
    "PixanoInferenceProvider",
]
