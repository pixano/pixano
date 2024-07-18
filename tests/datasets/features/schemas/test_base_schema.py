# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset import Dataset
from pixano.datasets.features import BaseSchema, NDArrayFloat, is_base_schema
from pixano.datasets.features.types.schema_reference import SchemaRef

from ..utils import make_tests_is_sublass_strict


class TestBaseSchema:
    def test_init(self):
        base_schema = BaseSchema()
        base_schema.id == ""

    def test_resolve_ref(self, dumb_dataset: Dataset):
        base_schema = BaseSchema()

        with pytest.raises(ValueError, match="Set the dataset before resolving a reference."):
            base_schema.resolve_ref(SchemaRef(id="", name=""))

        base_schema.dataset = dumb_dataset
        assert base_schema.resolve_ref(SchemaRef(id="0", name="item")) == dumb_dataset.schema.schemas["item"](
            id="0", split="test", metadata="metadata_0"
        )

        for id, name in [
            (
                "",
                "1",
            ),
            ("1", ""),
            ("", ""),
        ]:
            with pytest.raises(ValueError, match="Reference should have a name and an id."):
                base_schema.resolve_ref(SchemaRef(id=id, name=name))

    def test_serialize(self):
        class CustomSchema(BaseSchema):
            string: str
            integer: int
            list_of_strings: list[str]
            nd_array: NDArrayFloat
            list_of_nd_arrays: list[NDArrayFloat]

        json = CustomSchema.serialize()
        assert json == {
            "schema": "CustomSchema",
            "base_schema": "BaseSchema",
            "fields": {
                "id": {"type": "str", "collection": False},
                "string": {"type": "str", "collection": False},
                "integer": {"type": "int", "collection": False},
                "list_of_strings": {"type": "str", "collection": True},
                "nd_array": {"type": "NDArrayFloat", "collection": False},
                "list_of_nd_arrays": {"type": "NDArrayFloat", "collection": True},
            },
        }

    def test_deserialize(self):
        json = {
            "schema": "CustomSchema",
            "base_schema": "BaseSchema",
            "fields": {
                "id": {"type": "str", "collection": False},
                "string": {"type": "str", "collection": False},
                "integer": {"type": "int", "collection": False},
                "list_of_strings": {"type": "str", "collection": True},
                "nd_array": {"type": "NDArrayFloat", "collection": False},
                "list_of_nd_arrays": {"type": "NDArrayFloat", "collection": True},
            },
        }
        custom_schema = BaseSchema.deserialize(json)
        assert issubclass(custom_schema, BaseSchema)
        assert custom_schema.__name__ == "CustomSchema"
        assert set(custom_schema.model_fields.keys()) == {
            "id",
            "string",
            "integer",
            "list_of_strings",
            "nd_array",
            "list_of_nd_arrays",
        }

        custom_schema(
            id="",
            string="",
            integer=0,
            list_of_strings=["yolo"],
            nd_array=NDArrayFloat(values=[0.1], shape=[1, 1]),
            list_of_nd_arrays=[NDArrayFloat(values=[0.1], shape=[1, 1]), NDArrayFloat(values=[0.1], shape=[1, 1])],
        )


def test_is_base_schema():
    make_tests_is_sublass_strict(is_base_schema, BaseSchema)
