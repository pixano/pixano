# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .workspace import Workspace


class ImageVQAWorkspace(Workspace):
    """Image visual question answering workspace."""

    def validate_dataset_schema(self, schema):
        """Validate dataset schema."""
        return super().validate_dataset_schema(schema)
