# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class PDF(View):
    """PDF view.

    Attributes:
        url: The PDF URL. Empty when embedded.
        num_pages: The number of pages in the PDF.
        blob: Raw PDF bytes. Empty when using filesystem URL.
    """

    url: str = ""
    num_pages: int = 0
    blob: bytes = b""

    def open(self, media_dir: Path | None = None) -> bytes:
        """Open the PDF and return its raw bytes.

        Args:
            media_dir: Path to the media directory. If the URL is relative, it is relative to this directory.

        Returns:
            The raw PDF bytes.
        """
        if self.blob and len(self.blob) > 0:
            return self.blob
        if not self.url:
            raise ValueError("PDF has no blob data and no URL.")
        if media_dir is None:
            raise ValueError("media_dir is required when URL is set.")
        pdf_path = media_dir / self.url
        return pdf_path.read_bytes()


def is_pdf(cls: type, strict: bool = False) -> bool:
    """Check if the given class is `PDF` or a subclass of `PDF`."""
    return issubclass_strict(cls, PDF, strict)


def create_pdf(
    url: str = "",
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
    num_pages: int = 0,
    blob: bytes | None = None,
) -> PDF:
    """Create a `PDF` instance.

    Args:
        url: The PDF URL. Can be empty when using embedded blob.
        id: PDF ID.
        item_ref: Item reference.
        parent_ref: Parent view reference.
        num_pages: The number of pages in the PDF.
        blob: Raw PDF bytes.

    Returns:
        The created `PDF` instance.
    """
    return PDF(
        id=id,
        item_ref=item_ref,
        parent_ref=parent_ref,
        url=url,
        num_pages=num_pages,
        blob=blob or b"",
    )
