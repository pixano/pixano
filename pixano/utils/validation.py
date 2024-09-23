# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime


def issubclass_strict(obj: type, cls: type, strict: bool = False) -> bool:
    """Check if the given object is of the given class type or a subclass of the given class type.

    Args:
        obj: The object to check.
        cls: The class to compare against.
        strict: If True, the object must be of the given class type.

    Returns:
        True if the object is of the given class type or a subclass of the given class type.
    """
    if strict:
        return obj == cls
    return issubclass(obj, cls)


def validate_and_init_create_at_and_update_at(
    created_at: datetime | str | None, updated_at: datetime | str | None
) -> tuple[datetime, datetime]:
    """Validate and initialize created_at and updated_at.

    The validation and initialization of created_at and updated_at is done as follows:
    - If created_at is None, it is set to the current date and time.
    - If updated_at is None, it is set to created_at.
    - If updated_at is not None and created_at is None, a ValueError is raised.
    - If updated_at is not None and created_at is not None, updated_at should be greater than created_at.
    - If created_at and updated_at are provided as strings, they are converted to datetime objects from ISO format.

    Args:
        created_at: The creation date of the object.
        updated_at: The last modification date of the object.

    Returns:
        A tuple containing the created_at and updated_at.
    """
    if created_at is not None and not isinstance(created_at, datetime):
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            raise ValueError("created_at should be a datetime object or None.")
    if updated_at is not None and not isinstance(updated_at, datetime):
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        else:
            raise ValueError("updated_at should be a datetime object or None.")
    if updated_at is not None and created_at is None:
        raise ValueError("created_at should be set if updated_at is set.")
    elif created_at is not None:
        if updated_at is not None:
            if not isinstance(updated_at, datetime):
                raise ValueError("updated_at should be a datetime object.")
            elif updated_at < created_at:
                raise ValueError("updated_at should be greater than created_at.")
        else:
            updated_at = created_at
    elif created_at is None:
        created_at = datetime.now()
        updated_at = created_at
    return created_at, updated_at
