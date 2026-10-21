# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What every job kind that calls pixano-inference needs, whatever it asks of it.

Knowing whether a failed call is the server's fault or the medium's, and — when every medium of
a chunk is refused — asking the server itself with an image known to be good. Kinds differ in the
call they make, not in any of this.
"""

import io
from functools import cache
from typing import Any, Callable, Literal

import httpx
from PIL import Image
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient

from pixano.inference.media import bytes_to_data_uri

from ..reader import JobReader
from .base import TransientError


# The answers that say "come back later": timeout, too many requests, service unavailable. The
# client already replays 502, 503 and 504 on its own; what reaches this point has survived its
# retries and belongs to the queue.
TRANSIENT_STATUSES = frozenset({408, 429, 502, 503, 504})

# The answers that say "this request will never pass", whatever its content: no permission, no
# route, no model. Retrying another medium would change nothing.
REQUEST_STATUSES = frozenset({401, 403, 404, 405})

# The status the client gives an error when the server answered nothing at all — connection
# refused, timeout. It wraps it in a PixanoInferenceError rather than letting the httpx error
# through.
NO_RESPONSE = 0

# The code the client gives a successful answer it cannot read — not JSON, or not the schema it
# expects. The server and this worker disagree on the contract (two pixano-inference versions,
# say): no medium is at fault, and every call would fail the same way.
INVALID_RESPONSE = "invalid_response"

# Side of the witness image: the smallest the server accepts without arguing. It only serves to
# find out whether the server can still process an image known to be good, not to produce
# anything.
WITNESS_IMAGE_SIDE = 16

Failure = Literal["transient", "request", "medium"]


def classify(error: Exception) -> Failure:
    """Whose fault a failed call is: the server's for now, the request's for good, or the medium's.

    A medium is only blamed on an answer, never on silence: a server that does not answer, or
    asks to come back later, makes the call transient.

    Args:
        error: What the call raised.

    Returns:
        "transient" when the call may pass later, "request" when no medium would make it pass,
        "medium" when the server refused what it was sent.

    Raises:
        Exception: `error` itself, when it is neither a transport error nor an inference error:
            not a failure of the call to classify.
    """
    if isinstance(error, httpx.TransportError):
        return "transient"
    if isinstance(error, PixanoInferenceError):
        if error.status_code == NO_RESPONSE or error.status_code in TRANSIENT_STATUSES:
            return "transient"
        if error.status_code in REQUEST_STATUSES or error.code == INVALID_RESPONSE:
            return "request"
        return "medium"
    raise error


def transient_reason(error: Exception) -> str:
    """What a chunk handed back after a transient failure says: silence, or a request to come back later."""
    if isinstance(error, PixanoInferenceError) and error.status_code != NO_RESPONSE:
        return f"the inference asks to come back later: {error}"
    return f"the inference does not answer: {error}"


def refusal_detail(error: PixanoInferenceError) -> dict[str, Any]:
    """What the quarantine records of a medium the server refused."""
    return {"status": error.status_code, "code": error.code, "message": str(error.message)[:500]}


@cache
def witness_image() -> str:
    """A generated image, as bytes, that the server must be able to process.

    When every medium of a chunk is refused, it tells an inference outage from a chunk that is
    really corrupt: a threshold on the number of refused media made the decision depend on the
    chunk size, and the last chunk of a dataset often holds a single image.
    """
    image = Image.new("RGB", (WITNESS_IMAGE_SIDE, WITNESS_IMAGE_SIDE), (128, 128, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return bytes_to_data_uri(buffer.getvalue())


class InferenceServer:
    """The pixano-inference server a worker knows, as its job kinds see it."""

    def __init__(self, url: str, api_key: str) -> None:
        """Bind to a server.

        Args:
            url: The server's address.
            api_key: Its key, empty when it needs none.
        """
        self.url = url.rstrip("/")
        self.api_key = api_key

    def client(self, max_retries: int) -> SyncPixanoInferenceClient:
        """A client for one chunk's calls."""
        return SyncPixanoInferenceClient(self.url, api_key=self.api_key or None, max_retries=max_retries)


def blame_the_server_or_the_media(
    call: Callable[[str], Any],
    reader: JobReader,
    table: str,
    refused: list[str],
    by_path: dict[str, Any],
) -> None:
    """Decide, on a chunk whose every medium was refused, whether the server or the media are to blame.

    A witness image, generated here, is sent as bytes: refused, the server is not well and the
    chunk is replayed later. Accepted, the media are at fault — unless they had been designated
    by path: the server may not read the storage it was told to mount, and then refuses every
    path through no fault of any medium. So one of them is resent as bytes; if it passes, the
    mount is the cause, and the chunk is replayed with the reason, rather than three hundred
    healthy images going to quarantine.

    Args:
        call: The kind's call on one medium reference; it raises when the server refuses it.
        reader: Where to read a medium's bytes.
        table: The media's table.
        refused: The records whose medium was refused, by identifier.
        by_path: The view row of each medium sent by path, refused or not, by record identifier.

    Raises:
        TransientError: The server refuses the witness image, or does not read its media by path.
    """
    try:
        call(witness_image())
    except (httpx.TransportError, PixanoInferenceError) as error:
        raise TransientError(f"the inference refuses even the witness image: {error}") from error

    first_by_path = next((record_id for record_id in refused if record_id in by_path), None)
    if first_by_path is None:
        return
    found = reader.dataset.get_view_binary(table, by_path[first_by_path].id)
    if found is None or not found[0]:
        return
    try:
        call(bytes_to_data_uri(found[0]))
    except (httpx.TransportError, PixanoInferenceError):
        # Refused as bytes too: the medium really is at fault.
        return
    raise TransientError(
        f"the inference refuses media by path but accepts the same one as bytes ({first_by_path}): "
        "it does not read the media storage — check PIXANO_INFERENCE_MEDIA_ROOT and its mount"
    )
