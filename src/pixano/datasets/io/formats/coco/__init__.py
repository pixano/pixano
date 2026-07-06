# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""COCO instances format: two-pass streaming importer (spec §7.2)."""

from .importer import COCO, CocoImporter


__all__ = ["COCO", "CocoImporter"]
