# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features.schemas.schema_group import SchemaGroup

from .annotations import AnnotationModel
from .base_schema import BaseSchemaModel
from .embeddings import EmbeddingModel
from .entities import EntityModel
from .items import ItemModel
from .sources import SourceModel
from .views import ViewModel


_SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT: dict[SchemaGroup, type[BaseSchemaModel]] = {
    SchemaGroup.EMBEDDING: EmbeddingModel,
    SchemaGroup.ITEM: ItemModel,
    SchemaGroup.ENTITY: EntityModel,
    SchemaGroup.ANNOTATION: AnnotationModel,
    SchemaGroup.VIEW: ViewModel,
    SchemaGroup.SOURCE: SourceModel,
}
