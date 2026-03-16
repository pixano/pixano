# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import sys


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from pydantic import model_validator

from pixano.utils import issubclass_strict

from ..records import RecordComponent


class View(RecordComponent):
    """View base class.

    Views are used to define a view in a dataset such as an image, a point cloud, a text.

    Attributes:
        logical_name: Logical view name (sensor/modality identifier, e.g. "front_camera", "thermal", "lidar").
        uri: Resource locator (path, URL, or data URI). Empty when using embedded raw_bytes.
        raw_bytes: Embedded binary content. Empty when using URI.
        preview: Thumbnail/preview bytes.
        preview_format: Preview format (e.g. "jpeg", "png").
    """

    logical_name: str = ""
    uri: str = ""
    raw_bytes: bytes = b""
    preview: bytes = b""
    preview_format: str = ""

    @model_validator(mode="after")
    def _check_uri_or_raw_bytes(self) -> Self:
        if self.uri and self.raw_bytes:
            raise ValueError("Cannot set both 'uri' and 'raw_bytes' on a View. Use one or the other.")
        return self


def is_view(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `View` or subclass of `View`."""
    return issubclass_strict(cls, View, strict)
