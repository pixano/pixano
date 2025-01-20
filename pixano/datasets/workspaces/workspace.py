# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from abc import ABC
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pixano.datasets.dataset_schema import DatasetSchema


class Workspace(ABC):
    """Workspace."""

    def validate_dataset_schema(self, schema: "DatasetSchema"):
        """Validate dataset schema."""
        pass
