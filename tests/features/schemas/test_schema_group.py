# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from lancedb.pydantic import Vector

from pixano.features import Annotation, Embedding, Entity, Item, SchemaGroup, Source, View
from pixano.features.schemas.schema_group import group_to_str, schema_to_group


class Embedding8(Embedding):
    vector: Vector(8)


@pytest.mark.parametrize(
    "schema_type, expected",
    [
        (Entity(), SchemaGroup.ENTITY),
        (Entity, SchemaGroup.ENTITY),
        (Annotation(), SchemaGroup.ANNOTATION),
        (Annotation, SchemaGroup.ANNOTATION),
        (View(), SchemaGroup.VIEW),
        (View, SchemaGroup.VIEW),
        (Source(name="test", kind="model"), SchemaGroup.SOURCE),
        (Source, SchemaGroup.SOURCE),
        (Embedding8(vector=list(range(8))), SchemaGroup.EMBEDDING),
        (Embedding, SchemaGroup.EMBEDDING),
        (Item(), SchemaGroup.ITEM),
        (Item, SchemaGroup.ITEM),
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
        (SchemaGroup.SOURCE, False, "source"),
        (SchemaGroup.SOURCE, True, "sources"),
        (SchemaGroup.VIEW, False, "view"),
        (SchemaGroup.VIEW, True, "views"),
        (SchemaGroup.ANNOTATION, False, "annotation"),
        (SchemaGroup.ANNOTATION, True, "annotations"),
        (SchemaGroup.VIEW, False, "view"),
        (SchemaGroup.VIEW, True, "views"),
        (SchemaGroup.ITEM, False, "item"),
        (SchemaGroup.ITEM, True, "items"),
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
