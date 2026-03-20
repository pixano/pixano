# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from lancedb.pydantic import Vector

from pixano.features import Embedding, Entity, Record, SchemaGroup, View
from pixano.schemas.annotations.entity_annotation import EntityAnnotation
from pixano.schemas.schema_group import group_to_str, schema_to_group


class Embedding8(Embedding):
    vector: Vector(8)


@pytest.mark.parametrize(
    "schema_type, expected",
    [
        (Entity(), SchemaGroup.ENTITY),
        (Entity, SchemaGroup.ENTITY),
        (EntityAnnotation(), SchemaGroup.ANNOTATION),
        (EntityAnnotation, SchemaGroup.ANNOTATION),
        (View(), SchemaGroup.VIEW),
        (View, SchemaGroup.VIEW),
        (Embedding8(vector=list(range(8))), SchemaGroup.EMBEDDING),
        (Embedding, SchemaGroup.EMBEDDING),
        (Record(), SchemaGroup.RECORD),
        (Record, SchemaGroup.RECORD),
    ],
)
def test_schema_to_group(schema_type, expected):
    assert schema_to_group(schema_type) == expected


def test_schema_to_group_error():
    with pytest.raises(ValueError, match="Unknown schema type: 123456789"):
        schema_to_group(123456789)


@pytest.mark.parametrize(
    "group, plural, expected",
    [
        (SchemaGroup.VIEW, False, "view"),
        (SchemaGroup.VIEW, True, "views"),
        (SchemaGroup.ANNOTATION, False, "annotation"),
        (SchemaGroup.ANNOTATION, True, "annotations"),
        (SchemaGroup.RECORD, False, "record"),
        (SchemaGroup.RECORD, True, "records"),
        (SchemaGroup.EMBEDDING, False, "embedding"),
        (SchemaGroup.EMBEDDING, True, "embeddings"),
        (SchemaGroup.ENTITY, False, "entity"),
        (SchemaGroup.ENTITY, True, "entities"),
    ],
)
def test_group_to_str(group: SchemaGroup, plural: bool, expected: str):
    assert group_to_str(group, plural) == expected


def test_group_to_str_error():
    with pytest.raises(ValueError, match="Unknown schema group: unknown"):
        group_to_str("unknown", False)
