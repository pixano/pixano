# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


class DatasetPaginationError(ValueError):
    """Error raised when paginating a dataset."""

    pass


class DatasetOffsetLimitError(DatasetPaginationError):
    """Error raised when offset reached the limit while paginating a dataset."""

    pass


class DatasetAccessError(ValueError):
    """Error raised when accessing a dataset."""

    pass


class DatasetWriteError(ValueError):
    """Error raised when writing to a dataset."""

    pass