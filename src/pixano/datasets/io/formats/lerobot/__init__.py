# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""LeRobot format: episodes as annotatable frame sequences (spec §7.3)."""

from .importer import LEROBOT, LeRobotImporter


__all__ = ["LEROBOT", "LeRobotImporter"]
