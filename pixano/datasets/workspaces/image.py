# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.dataset_schema import DatasetSchema

from .workspace import Workspace


class ImageWorkspace(Workspace):
    """Image workspace."""

    def validate_dataset_schema(self, schema: DatasetSchema):
        """Validate dataset schema."""
        return super().validate_dataset_schema(schema)
