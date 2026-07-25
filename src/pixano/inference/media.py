# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Media helpers for inference requests.

The pixano-inference `/v1` API accepts images (and video frames) as strings — a path, an
http(s) URL, or a base64 data-URI. When Pixano holds raw embedded bytes, they are encoded as a
``data:<mime>;base64,<...>`` URI here (with a small magic-number mime sniff).
"""

import base64


def detect_image_mime(data: bytes) -> str:
    """Infer an image MIME type from its leading magic bytes (defaults to PNG)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    return "image/png"


def bytes_to_data_uri(data: bytes) -> str:
    """Encode raw image bytes as a base64 ``data:`` URI with a sniffed MIME type."""
    mime = detect_image_mime(data)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"
