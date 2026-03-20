# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Schema serialization utilities for table schemas.

This module provides helpers to serialize and deserialize LanceModel-based
table schemas to/from JSON-compatible dicts.  These are used by
:class:`DatasetInfo` to persist the ``tables`` mapping in ``info.json``.
"""

from base64 import b64decode, b64encode
from datetime import datetime
from typing import Any, get_args, get_origin

from lancedb.pydantic import FixedSizeListMixin, LanceModel, Vector
from pydantic import BaseModel, Field, create_model
from pydantic_core import PydanticUndefined

from pixano.features.pyarrow_utils import DESERIALIZE_PYARROW_DATATYPE, SERIALIZE_PYARROW_DATATYPE
from pixano.features.types.nd_array_float import NDArrayFloat
from pixano.schemas import CANONICAL_SCHEMA_MAP, BaseIntrinsics, Extrinsics, Intrinsics


# ---------------------------------------------------------------------------
# Manifest type registry (for annotation serialization/deserialization)
# ---------------------------------------------------------------------------

_MANIFEST_TYPES: dict[str, type] = {
    "bool": bool,
    "bytes": bytes,
    "bytearray": bytearray,
    "complex": complex,
    "datetime": datetime,
    "float": float,
    "int": int,
    "memoryview": memoryview,
    "str": str,
    "NDArrayFloat": NDArrayFloat,
    "BaseIntrinsics": BaseIntrinsics,
    "Intrinsics": Intrinsics,
    "Extrinsics": Extrinsics,
}


_TIMESTAMP_EXCLUDE = {"created_at": True, "updated_at": True}


class DatasetItem(BaseModel):
    """Legacy compatibility model for item-centric tests and fixtures."""

    id: str = ""
    split: str = "default"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def to_dataset_schema(cls):
        """Convert to dataset schema (unsupported legacy method)."""
        raise NotImplementedError("DatasetItem compatibility methods are not supported by the record-based API.")

    @classmethod
    def from_dataset_schema(cls, schema):
        """Build from dataset schema (unsupported legacy method)."""
        raise NotImplementedError("DatasetItem compatibility methods are not supported by the record-based API.")

    def to_schemas_data(self, schema):
        """Convert to schemas data (unsupported legacy method)."""
        raise NotImplementedError("DatasetItem compatibility methods are not supported by the record-based API.")


def build_model_dump_exclude_timestamps(model: BaseModel) -> dict[str, Any]:
    """Build a native Pydantic exclude map that removes timestamps recursively."""
    exclude: dict[str, Any] = dict(_TIMESTAMP_EXCLUDE)
    for field_name in type(model).model_fields:
        value = getattr(model, field_name, None)
        if isinstance(value, BaseModel):
            exclude[field_name] = build_model_dump_exclude_timestamps(value)
        elif isinstance(value, list):
            nested = [item for item in value if isinstance(item, BaseModel)]
            if nested:
                exclude[field_name] = {"__all__": build_model_dump_exclude_timestamps(nested[0])}
    return exclude


# ---------------------------------------------------------------------------
# Field-level helpers
# ---------------------------------------------------------------------------


def _field_definition(annotation: Any, field_info: Any) -> tuple[Any, Any]:
    if field_info.default_factory is not None:
        return annotation, Field(default_factory=field_info.default_factory)
    if field_info.default is not PydanticUndefined:
        return annotation, field_info.default
    return annotation, ...


def _field_definition_from_info(field_info: Any) -> tuple[Any, Any]:
    return _field_definition(field_info.annotation, field_info)


def _encode_manifest_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": b64encode(value).decode("ascii")}
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_encode_manifest_default(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode_manifest_default(item) for key, item in value.items()}
    return value


def _decode_manifest_default(value: Any) -> Any:
    if isinstance(value, dict):
        if "__bytes__" in value:
            return b64decode(value["__bytes__"])
        return {key: _decode_manifest_default(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_manifest_default(item) for item in value]
    return value


def _field_base_annotation(annotation: Any) -> tuple[bool, Any]:
    origin = get_origin(annotation)
    if origin in (list, tuple):
        args = get_args(annotation)
        if not args:
            raise ValueError(f"Collection annotation '{annotation}' is missing inner type.")
        return True, args[0]
    return False, annotation


def _serialize_annotation(annotation: Any) -> dict[str, Any]:
    collection, inner = _field_base_annotation(annotation)
    payload: dict[str, Any] = {
        "collection": collection,
    }

    if get_origin(inner) is None and isinstance(inner, type) and issubclass(inner, FixedSizeListMixin):
        payload["type"] = "FixedSizeList"
        payload["dim"] = inner.dim()  # type: ignore[attr-defined]
        payload["value_type"] = SERIALIZE_PYARROW_DATATYPE[inner.value_arrow_type()]  # type: ignore[attr-defined]
        return payload

    if get_origin(inner) is not None:
        if get_origin(inner).__name__ == "Literal":
            payload["type"] = "str"
            return payload
        raise ValueError(f"Unsupported field annotation '{annotation}'.")

    if not isinstance(inner, type):
        raise ValueError(f"Unsupported field annotation '{annotation}'.")

    payload["type"] = inner.__name__
    return payload


def _deserialize_annotation(payload: dict[str, Any]) -> Any:
    type_name = payload["type"]
    if type_name == "FixedSizeList":
        annotation = Vector(payload["dim"], DESERIALIZE_PYARROW_DATATYPE[payload["value_type"]])
    elif type_name in _MANIFEST_TYPES:
        annotation = _MANIFEST_TYPES[type_name]
    else:
        raise ValueError(f"Type '{type_name}' not registered in schema manifest.")

    if payload["collection"]:
        return list[annotation]  # type: ignore[valid-type]
    return annotation


def _serialize_field(field_name: str, field_info: Any) -> dict[str, Any]:
    payload = _serialize_annotation(field_info.annotation)
    payload["required"] = field_info.is_required()

    if not field_info.is_required() and field_info.default is not PydanticUndefined:
        payload["default"] = _encode_manifest_default(field_info.default)

    return payload


def _field_matches_base(field_name: str, field_info: Any, base_field: Any | None) -> bool:
    if base_field is None:
        return False
    return _serialize_field(field_name, field_info) == _serialize_field(field_name, base_field)


def _manifest_field_matches_base(field_name: str, payload: dict[str, Any], base_field: Any | None) -> bool:
    if base_field is None:
        return False
    return payload == _serialize_field(field_name, base_field)


def _coerce_manifest_default(default: Any, annotation: Any, collection: bool) -> Any:
    if collection:
        if not isinstance(default, list):
            return default
        inner = annotation
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return [inner.model_validate(item) if isinstance(item, dict) else item for item in default]  # type: ignore[attr-defined]
        return default

    if isinstance(annotation, type) and issubclass(annotation, BaseModel) and isinstance(default, dict):
        return annotation.model_validate(default)  # type: ignore[attr-defined]

    return default


def _deserialize_field(base_type: type[LanceModel], field_name: str, payload: dict[str, Any]) -> tuple[Any, Any]:
    annotation = _deserialize_annotation(payload)
    required = payload["required"]
    collection = payload["collection"]
    base_annotation = get_args(annotation)[0] if collection else annotation

    if required:
        return annotation, ...

    if "default" in payload:
        default = _decode_manifest_default(payload["default"])
        default = _coerce_manifest_default(default, base_annotation, collection)
        return annotation, default

    base_field = base_type.model_fields.get(field_name)
    if base_field is None:
        raise ValueError(f"Field '{field_name}' is missing a default in schema manifest.")

    return _field_definition(annotation, base_field)


# ---------------------------------------------------------------------------
# Table-level serialization
# ---------------------------------------------------------------------------


def _serialize_table_schema(schema: type[LanceModel]) -> dict[str, Any]:
    """Serialize a LanceModel schema to a JSON-compatible dict.

    The output contains a ``"base"`` key (the canonical Pixano base type name)
    and a ``"fields"`` dict with only the fields that differ from the base.
    If the schema is a custom subclass, a ``"name"`` key is also included.

    Args:
        schema: The schema class to serialize.

    Returns:
        Serialized schema dict.
    """
    from pixano.utils import get_super_type_from_dict

    base_type = get_super_type_from_dict(schema, CANONICAL_SCHEMA_MAP)
    if base_type is None:
        raise ValueError(f"Schema {schema.__name__} does not have a canonical Pixano base type.")

    payload: dict[str, Any] = {
        "base": base_type.__name__,
        "fields": {
            field_name: _serialize_field(field_name, field_info)
            for field_name, field_info in schema.model_fields.items()  # type: ignore[attr-defined]
            if not _field_matches_base(field_name, field_info, base_type.model_fields.get(field_name))  # type: ignore[attr-defined]
        },
    }

    if schema is not base_type:
        payload["name"] = schema.__name__

    return payload


def _deserialize_table_schema(payload: dict[str, Any]) -> type[LanceModel]:
    """Deserialize a JSON dict back into a LanceModel schema class.

    Args:
        payload: Serialized schema dict (from :func:`_serialize_table_schema`).

    Returns:
        The deserialized schema class.
    """
    base_name = payload["base"]
    base_type = CANONICAL_SCHEMA_MAP.get(base_name)
    if base_type is None:
        raise ValueError(f"Base schema '{base_name}' not found in registry.")

    model_name = payload.get("name")
    if model_name is None:
        return base_type

    fields = {
        field_name: _deserialize_field(base_type, field_name, field_payload)
        for field_name, field_payload in payload["fields"].items()
        if not _manifest_field_matches_base(field_name, field_payload, base_type.model_fields.get(field_name))
    }
    return create_model(model_name, __base__=base_type, **fields)
