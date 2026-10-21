# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What we give the inference to designate a media.

The plan wants media never to transit through Pixano: on a dataset of several terabytes,
sending the bytes saturates the network where a path is enough. But a dataset imported in
`embed` mode carries its images **inside** LanceDB, and there is then no path to give — that
is the case of the datasets in place today, and the existing embeddings computation works
precisely because it sends the bytes.

This module therefore applies a **preference, not a prohibition**: the path when it exists,
the bytes when that is the only route. And it says which of the two it chose, so that the
cost is measurable and visible in the logs instead of being discovered on a large dataset.
"""

import logging
import os
import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal, Protocol

from pixano.inference.media import bytes_to_data_uri


logger = logging.getLogger("pixano-worker")

# What the inference knows how to fetch by itself. Other schemes make no sense to it: a local
# path is only worth something if it is under a root it has declared.
REMOTE_SCHEMES = ("http://", "https://", "s3://")

# How a medium is designated to the inference. Each form fails in its own way, so each is
# diagnosed in its own way when the inference refuses every medium of a chunk: a path can be
# resent as the bytes this worker reads, a URL cannot be checked like that, and bytes have
# already travelled.
Designation = Literal["path", "url", "bytes"]


class MediaSource(Protocol):
    """The little that is needed from a dataset to fetch an embedded media."""

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        """The bytes of a view, and their type, or None."""
        ...


@dataclass(frozen=True)
class ResolvedMedia:
    """What we pass to the inference, and how we got there.

    Attributes:
        value: A path, a URL, or a data URI — the three forms the endpoint accepts.
        designation: Which of the three `value` is. Said rather than guessed from `value`: what
            can be checked when the inference refuses a medium depends on it.
        reason: Why this form, so that a log says something useful.
    """

    value: str
    designation: Designation
    reason: str

    @property
    def carried_bytes(self) -> bool:
        """True if the bytes went through this process.

        That is the cost we are trying to avoid, hence the one that must be countable.
        """
        return self.designation == "bytes"


class MediaResolver:
    """Translates a media reference into what the inference knows how to read.

    Attributes:
        media_root: The media root as this worker sees it.
        inference_media_root: The same root, as the inference sees it. The two differ as soon
            as the two processes do not mount the storage at the same place.
    """

    def __init__(self, media_root: str, inference_media_root: str) -> None:
        """Bind a resolver to the two views of the same storage."""
        self.media_root = media_root.rstrip("/")
        self.inference_media_root = inference_media_root.rstrip("/")

    @classmethod
    def unconfigured(cls) -> "MediaResolver":
        """A resolver that refuses to designate anything, and says so.

        For the execution paths with no deployment behind them — the engine's tests, whose
        kinds open no media. The former fallback, two hard-coded `/medias` roots, was the
        compose containers' path slipped into the code: a worker launched by hand without a
        configured root would have sent the inference paths it could not read.
        """
        return _UnconfiguredMedia()

    def resolve(self, source: MediaSource, table_name: str, view: Any) -> ResolvedMedia | None:
        """Designate a media for the inference.

        The order is a preference: what avoids carrying bytes comes first.

        Args:
            source: What to read an embedded media from.
            table_name: The view's table, to fetch its bytes.
            view: The view row — it carries `uri` or `raw_bytes`, never both.

        Returns:
            What to call the inference with, or None if this media cannot be found.
        """
        uri = (getattr(view, "uri", "") or "").strip()

        if uri.startswith(REMOTE_SCHEMES):
            return ResolvedMedia(uri, designation="url", reason="URL the inference knows how to read")

        if uri:
            translated = self.translate(uri)
            if translated is not None:
                return ResolvedMedia(translated, designation="path", reason="path under the declared root")
            # Outside the declared roots, the inference would refuse the path. The bytes are the
            # only route left, and the log says why we take it.
            logger.debug("media %s outside %s: sending the bytes", uri, self.media_root)

        return self._inline(source, table_name, view, uri)

    def path_refusal_diagnostic(self) -> str:
        """What to check when the inference refuses this resolver's paths but accepts the same medium as bytes.

        Said here, beside the path designation, because only the resolver knows where the
        inference's side of a path comes from. A source of media with another designation will
        say what to check for its own.
        """
        # A root of "/" was stripped to nothing at construction.
        return (
            f"it does not read the media storage under {self.inference_media_root or '/'} — "
            "check PIXANO_INFERENCE_MEDIA_ROOT on this worker, PIXANO_INFERENCE_MEDIA_ROOTS on the inference, "
            "and its mount"
        )

    def local_path(self, view: Any) -> str | None:
        """The file a view names, as this worker sees it, if it is under the media root.

        For what the worker must read itself rather than send — a medium's bytes, resent when
        the inference refuses its path. A relative reference is taken from the media root.

        The file must be under the root once links are followed, the root's own included: the
        check is on the real path, since opening the file follows them. On the path's text alone,
        a link under the root to a file outside it was read, and resent to the inference as a
        medium.
        """
        uri = (getattr(view, "uri", "") or "").strip()
        if not uri or uri.startswith(REMOTE_SCHEMES) or not self.media_root:
            return None
        clean = posixpath.normpath(posixpath.join(self.media_root, uri))
        real = PurePosixPath(os.path.realpath(clean))
        return clean if real.is_relative_to(PurePosixPath(os.path.realpath(self.media_root))) else None

    def translate(self, path: str) -> str | None:
        """Go from a path as seen by the worker to a path as seen by the inference.

        The path is normalised before being compared to the root. The `PurePosixPath`
        comparison is lexical: without normalisation, `/medias/../etc/passwd` passed for a
        path under `/medias`, and went as is to the inference.

        Returns:
            The translated path, or None if this path is not under the declared root — in which
            case the inference would refuse it, and it is better to know here.
        """
        clean = PurePosixPath(posixpath.normpath(path))
        root = PurePosixPath(self.media_root)
        if not clean.is_absolute() or not clean.is_relative_to(root):
            return None
        return str(PurePosixPath(self.inference_media_root) / clean.relative_to(root))

    def _inline(self, source: MediaSource, table_name: str, view: Any, uri: str) -> ResolvedMedia | None:
        """Fetch the media's bytes and encode them.

        This is the route of datasets imported in `embed` mode, whose images live in LanceDB.
        It is expensive on a large dataset, and that is why it comes last — but it is
        indispensable: without it, the datasets in place could not be processed at all.
        """
        found = source.get_view_binary(table_name, view.id)
        if found is None or not found[0]:
            return None
        reason = "embedded bytes" if not uri else "path outside the root, bytes sent"
        return ResolvedMedia(bytes_to_data_uri(found[0]), designation="bytes", reason=reason)


class _UnconfiguredMedia(MediaResolver):
    def __init__(self) -> None:
        super().__init__(media_root="", inference_media_root="")

    def resolve(self, source: MediaSource, table_name: str, view: Any) -> ResolvedMedia | None:
        raise RuntimeError("no media root configured: PIXANO_MEDIA_ROOT and PIXANO_INFERENCE_MEDIA_ROOT are empty")
