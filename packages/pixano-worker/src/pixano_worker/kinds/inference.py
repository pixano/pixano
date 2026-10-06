# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What every job kind that calls pixano-inference needs, whatever it asks of it.

Knowing whether a model is served before a job starts, which checkpoint answered for the
provenance of its rows, whether a failed call is the server's fault or the medium's, and — when
every medium of a chunk is refused — asking the server itself with an image known to be good.
The embeddings and detection kinds differ in the call they make, not in any of this.
"""

import io
import logging
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Callable, Literal

import httpx
from PIL import Image
from pixano_inference_client import PixanoInferenceError, SyncPixanoInferenceClient

from pixano.inference.media import bytes_to_data_uri

from ..reader import JobReader
from ..writer import ModelIdentity
from .base import TransientError


log = logging.getLogger("pixano-worker")

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

# How long a question about the server — which models it serves, which checkpoint — may take.
# The answer only gates a plan or completes a provenance: a slow server must not hold either for
# the client's default minute.
QUERY_TIMEOUT_S = 5.0

# Side of the witness image: the smallest the server accepts without arguing. It only serves to
# find out whether the server still answers, not to produce anything.
WITNESS_IMAGE_SIDE = 16

Failure = Literal["transient", "request", "medium"]

# Why a medium goes to quarantine, as its record in the queue says it.
MEDIA_NOT_FOUND = "media not found"
REFUSED_BY_THE_SERVER = "refused by the inference server"


def quarantined_item(item_id: str, reason: str, record_id: str | None = None, **detail: Any) -> dict[str, Any]:
    """A medium set aside, as a kind's result carries it: its record in the detail, when known."""
    if record_id is not None:
        detail["record_id"] = record_id
    return {"item_id": item_id, "reason": reason, **({"detail": detail} if detail else {})}


@dataclass
class ChunkMedia:
    """The media of a chunk, found and designated for the inference, and those set aside.

    Attributes:
        media: Each medium found, with the reference the inference will read it by.
        quarantined: The media that could not be found, with their record when known.
        by_path: The media designated by path, by identifier: one can be resent as bytes if
            the server refuses them all (see `blame_the_server_or_the_media`).
        carried_bytes: How many were sent as bytes — the cost the paths avoid.
    """

    media: list[tuple[Any, str]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    by_path: dict[str, Any] = field(default_factory=dict)
    carried_bytes: int = 0


def chunk_media(reader: JobReader, table: str, view_ids: list[str]) -> ChunkMedia:
    """Find a chunk's media and designate each for the inference, what every kind does first."""
    views = {row.id: row for row in reader.rows(table, view_ids)} if view_ids else {}
    found = ChunkMedia()
    for view_id in view_ids:
        view = views.get(view_id)
        if view is None:
            found.quarantined.append(quarantined_item(view_id, MEDIA_NOT_FOUND))
            continue
        resolved = reader.resolve_media(table, view)
        if resolved is None:
            found.quarantined.append(quarantined_item(view_id, MEDIA_NOT_FOUND, view.record_id))
            continue
        found.media.append((view, resolved.value))
        found.carried_bytes += int(resolved.carried_bytes)
        if not resolved.carried_bytes:
            found.by_path[view_id] = view
    return found


def classify(error: Exception) -> Failure:
    """Whose fault a failed call is: the server's for now, the request's for good, or the medium's.

    A medium is only blamed on an answer, never on silence: a server that does not answer, or
    asks to come back later, makes the call transient.
    """
    if isinstance(error, httpx.TransportError):
        return "transient"
    if isinstance(error, PixanoInferenceError):
        if error.status_code == NO_RESPONSE or error.status_code in TRANSIENT_STATUSES:
            return "transient"
        if error.status_code in REQUEST_STATUSES:
            return "request"
        return "medium"
    raise error


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
        self._checkpoints: dict[str, str] = {}

    def client(self, max_retries: int, timeout: float | None = None) -> SyncPixanoInferenceClient:
        """A client for one chunk's calls."""
        if timeout is None:
            return SyncPixanoInferenceClient(self.url, api_key=self.api_key or None, max_retries=max_retries)
        return SyncPixanoInferenceClient(
            self.url, api_key=self.api_key or None, max_retries=max_retries, timeout=timeout
        )

    def require_served(self, model: str, capability: str) -> None:
        """Refuse a job whose model the server does not serve with this capability.

        A server that cannot be reached is not a refusal: it may be restarting, and the chunks
        will wait for it like after any outage.

        Raises:
            ValueError: The server serves no such model, the models it serves named.
        """
        try:
            with self.client(max_retries=0, timeout=QUERY_TIMEOUT_S) as client:
                served = client.list_models()
        except Exception as error:  # noqa: BLE001 — an unreachable server is the chunks' concern
            log.warning("model '%s': cannot ask the inference whether it is served (%s)", model, error)
            return
        names = sorted(info.name for info in served if info.capability == capability)
        if model not in names:
            raise ValueError(
                f"the inference serves no {capability} model named '{model}' — it serves "
                f"{', '.join(names) or 'none'}. Deploy the model on pixano-inference, or choose one of those."
            )

    def model_identity(self, model: str) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it.

        The server declares no version as such; the checkpoint path is what identifies which
        weights answered. Asked once per model per process, and only a successful answer is
        remembered: a server that could not be asked is asked again on the next chunk rather
        than leaving every later row without a version.
        """
        if model not in self._checkpoints:
            checkpoint = self._checkpoint_of(model)
            if checkpoint is None:
                return ModelIdentity(model)
            self._checkpoints[model] = checkpoint
        return ModelIdentity(model, self._checkpoints[model])

    def _checkpoint_of(self, model: str) -> str | None:
        try:
            with self.client(max_retries=0, timeout=QUERY_TIMEOUT_S) as client:
                for info in client.list_models():
                    if info.name == model:
                        return info.model_path or None
        except Exception as error:  # noqa: BLE001 — a provenance that cannot be completed must not fail the chunk
            log.warning("model '%s': cannot ask the inference for its checkpoint (%s)", model, error)
        return None


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
        refused: The identifiers of the refused media.
        by_path: The refused media sent by path, by identifier, with their view row.

    Raises:
        TransientError: The server refuses the witness image, or does not read its media by path.
    """
    try:
        call(witness_image())
    except (httpx.TransportError, PixanoInferenceError) as error:
        raise TransientError(f"the inference refuses even the witness image: {error}") from error

    first_by_path = next((view_id for view_id in refused if view_id in by_path), None)
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
