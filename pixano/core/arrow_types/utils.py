import pyarrow as pa


def convert_field(
    field_name: str, field_type: pa.DataType, field_data: list
) -> pa.Array:
    """Convert PyArrow ExtensionTypes properly

    Args:
        field_name (str): Name
        field_type (pa.DataType): Target PyArrow format
        field_data (list): Data in Python format

    Returns:
        pa.Array: Data in target PyArrow format
    """

    # If target format is an ExtensionType
    if isinstance(field_type, pa.ExtensionType):
        storage = pa.array(field_data, type=field_type.storage_type)
        return pa.ExtensionArray.from_storage(field_type, storage)

    # If target format is an extension of ListType
    elif pa.types.is_list(field_type):
        native_arr = pa.array(field_data)
        if isinstance(native_arr, pa.NullArray):
            return pa.nulls(len(native_arr), field_type)
        offsets = native_arr.offsets
        values = native_arr.values.to_numpy(zero_copy_only=False)
        return pa.ListArray.from_arrays(
            offsets,
            convert_field(f"{field_name}.elements", field_type.value_type, values),
        )

    # If target format is an extension of StructType
    elif pa.types.is_struct(field_type):
        native_arr = pa.array(field_data)
        if isinstance(native_arr, pa.NullArray):
            return pa.nulls(len(native_arr), field_type)
        arrays = []
        for subfield in field_type:
            sub_arr = native_arr.field(subfield.name)
            converted = convert_field(
                f"{field_name}.{subfield.name}",
                subfield.type,
                sub_arr.to_numpy(zero_copy_only=False),
            )
            arrays.append(converted)
        return pa.StructArray.from_arrays(arrays, fields=field_type)

    # For other target formats
    else:
        return pa.array(field_data, type=field_type)


def register_extension_types(pa_types):
    """Register PyArrow ExtensionTypes"""

    for t in pa_types:
        # Register ExtensionType
        try:
            pa.register_extension_type(t())
        # If ExtensionType is already registered
        except pa.ArrowKeyError:
            pass


def fields(type: pa.DataType) -> list:
    Fields = []
    for f in range(type().storage_type.num_fields):
        Fields.append(type().storage_type.field(f))
    return Fields


def is_number(t: pa.DataType) -> bool:
    """Check if DataType is a a number (integer or float)

    Args:
        t (pa.DataType): DataType to check

    Returns:
        bool: True if DataType is an integer or a float
    """

    return pa.types.is_integer(t) or pa.types.is_floating(t)
