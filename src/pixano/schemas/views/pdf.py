# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from pixano.utils import issubclass_strict

from .view import View


class PDF(View):
    """PDF view.

    Attributes:
        num_pages: The number of pages in the PDF.
    """

    num_pages: int = 0

    def open(self) -> bytes:
        """Open the PDF and return its raw bytes.

        The PDF data is read from the embedded ``raw_bytes`` field. If
        ``raw_bytes`` is empty but ``uri`` is set, it is treated as an
        absolute filesystem path or a remote URI.

        Returns:
            The raw PDF bytes.
        """
        if self.raw_bytes and len(self.raw_bytes) > 0:
            return self.raw_bytes
        if not self.uri:
            raise ValueError("PDF has no raw_bytes and no URI.")
        parsed = urlparse(self.uri)
        if parsed.scheme in ("http", "https", "s3"):
            return urlopen(self.uri).read()
        return Path(self.uri).read_bytes()


def is_pdf(cls: type, strict: bool = False) -> bool:
    """Check if the given class is `PDF` or a subclass of `PDF`."""
    return issubclass_strict(cls, PDF, strict)


def create_pdf(
    uri: str = "",
    id: str = "",
    record_id: str = "",
    logical_name: str = "",
    num_pages: int = 0,
    raw_bytes: bytes | None = None,
    preview: bytes = b"",
    preview_format: str = "",
) -> PDF:
    """Create a `PDF` instance.

    Args:
        uri: The PDF URI. Can be empty when using embedded raw_bytes.
        id: PDF ID.
        record_id: Record ID.
        logical_name: Logical view name.
        num_pages: The number of pages in the PDF.
        raw_bytes: Raw PDF bytes.
        preview: Thumbnail/preview bytes.
        preview_format: Preview format (e.g. "jpeg", "png").

    Returns:
        The created `PDF` instance.
    """
    return PDF(
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        uri=uri,
        num_pages=num_pages,
        raw_bytes=raw_bytes or b"",
        preview=preview,
        preview_format=preview_format,
    )
