"""Binary media helpers for API routes."""

from collections.abc import Iterable, Iterator


FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "PNG": "image/png",
    "png": "image/png",
    "WEBP": "image/webp",
    "webp": "image/webp",
    "TIFF": "image/tiff",
    "tiff": "image/tiff",
    "BMP": "image/bmp",
    "bmp": "image/bmp",
    "GIF": "image/gif",
    "gif": "image/gif",
    "pdf": "application/pdf",
    "PDF": "application/pdf",
    "ply": "application/x-ply",
    "pcd": "application/x-pcd",
}

MULTIPART_BOUNDARY = b"frame_boundary"


def media_type_from_format(media_format: str | None) -> str:
    """Map a media format string to a MIME type."""

    if not media_format:
        return "application/octet-stream"
    return FORMAT_TO_MIME.get(media_format, "application/octet-stream")


def iter_multipart_frames(frames: Iterable[tuple[int, bytes, str]]) -> Iterator[bytes]:
    """Yield a multipart stream for temporal frame binaries."""

    for frame_index, payload, media_type in frames:
        header = (
            b"--" + MULTIPART_BOUNDARY + b"\r\n"
            b"Content-Type: " + media_type.encode() + b"\r\n"
            b"Content-Length: " + str(len(payload)).encode() + b"\r\n"
            b"X-Frame-Index: " + str(frame_index).encode() + b"\r\n"
            b"\r\n"
        )
        yield header
        yield payload
        yield b"\r\n"

    yield b"--" + MULTIPART_BOUNDARY + b"--\r\n"
