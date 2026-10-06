# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Worker configuration, read from the environment.

The worker never assumes where its dependencies run: it only knows addresses. This is what
lets the same binary run in the local compose, next to a NAS and a GPU server in lab mode,
or in the cloud — without a code change.

Variables without a default value are mandatory: a default that is only right locally does
not raise an error at startup, it silently connects the worker to the wrong place and fails
three layers further.
"""

import os
import re
from dataclasses import dataclass
from typing import Callable, TypeVar
from urllib.parse import urlsplit, urlunsplit


# Ephemeral file, local to the container: its modification time is the liveness probe.
_HEARTBEAT_PATH_DEFAULT = "/tmp/pixano-worker.heartbeat"  # noqa: S108

# Age beyond which a worker is considered dead. The worker must beat more often than this
# whatever it does: see MAX_BACKOFF_S, which derives from it.
MAX_HEARTBEAT_AGE_S = 30.0


# Chunks executed at a time by default. A chunk's time is mostly spent waiting for the
# inference, so several in-flight chunks fill a server that a single one would leave almost
# empty. Four is a cautious starting point, not a measurement: the right value depends on the
# inference server this worker shares, and is tuned per deployment.
DEFAULT_CONCURRENCY = 4

# Duration beyond which a chunk is held to be hung and handed back to the queue. It must exceed
# the legitimate worst case of a job kind, otherwise we would hand back slow but healthy work.
# For embeddings, a call that times out is worth `request_timeout_s` × (1 + `max_retries`), that
# is twenty minutes with the default timeouts — then the chunk is handed back as transient,
# without looking for a faulty image. Half an hour covers this case and still frees a hung chunk
# within the morning. A slow server that *answers* 500 on every call can do more (up to seven
# calls to isolate one image out of eight): the limit is then what applies, and that is intended.
DEFAULT_CHUNK_TIMEOUT_S = 1800.0

# The demonstration job kinds — `fake`, which computes nothing, and `label`, which sets an
# arbitrary label — have no business in a shared deployment: their `write_to` parameter lets
# them write into any table of a dataset. Absent by default; the local compose enables them for
# the demo and the tests.
DEMO_KINDS_FLAG = "PIXANO_WORKER_DEMO_KINDS"


def heartbeat_path() -> str:
    """Location of the heartbeat file, shared by the worker and its probe."""
    return os.environ.get("PIXANO_WORKER_HEARTBEAT", _HEARTBEAT_PATH_DEFAULT)


class MissingConfigurationError(RuntimeError):
    """A mandatory environment variable is absent or empty."""


def _required(name: str, hint: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingConfigurationError(f"{name} is mandatory — {hint}")
    return value


NumberT = TypeVar("NumberT", int, float)


def _flag(name: str) -> bool:
    """An environment flag: true for `1`, `true`, `yes`, `on`, false otherwise."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _positive(name: str, default: NumberT, cast: Callable[[str], NumberT]) -> NumberT:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        value = cast("0")
    if value <= 0:
        raise MissingConfigurationError(f"{name} must be a strictly positive number, got '{raw}'")
    return value


# psycopg accepts two spellings: the URL (postgresql://...) and libpq's keyword form
# (host=... password=...). Both must be masked, otherwise a password ends up in clear in the
# logs the day someone configures the second one.
_KEYWORD_PASSWORD = re.compile(r"(?i)\bpassword\s*=\s*(?:'(?:[^'\\]|\\.)*'|\S+)")


def redact_dsn(dsn: str) -> str:
    """Replace the password of a connection string with asterisks."""
    parts = urlsplit(dsn)
    if parts.password is not None:
        user = f"{parts.username}:***" if parts.username else "***"
        port = f":{parts.port}" if parts.port else ""
        return urlunsplit(parts._replace(netloc=f"{user}@{parts.hostname or ''}{port}"))
    return _KEYWORD_PASSWORD.sub("password=***", dsn)


@dataclass(frozen=True)
class WorkerConfig:
    """Everything the worker must know about its deployment environment.

    Attributes:
        database_url: PostgreSQL connection URL — job queue, state and events.
        inference_url: URL of the pixano-inference server.
        inference_api_key: API key of the inference. Empty when it is not protected.
        library_dir: Directory of the LanceDB library, as seen by the worker.
        media_root: Media root as the worker sees it.
        inference_media_root: The same root, as the inference sees it. The worker translates
            from one to the other before each call: the two sides do not necessarily mount
            the same storage at the same place.
        heartbeat_path: File whose freshness serves as the liveness probe.
        concurrency: Number of chunks executed at a time.
        chunk_timeout_s: Maximum duration of a chunk, beyond which it is handed back to the queue.
    """

    database_url: str
    inference_url: str
    inference_api_key: str
    library_dir: str
    media_root: str
    inference_media_root: str
    heartbeat_path: str
    concurrency: int = DEFAULT_CONCURRENCY
    chunk_timeout_s: float = DEFAULT_CHUNK_TIMEOUT_S
    demo_kinds: bool = False

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Build the configuration from the environment, or fail clearly."""
        return cls(
            database_url=_required("PIXANO_DATABASE_URL", "PostgreSQL connection URL"),
            inference_url=_required("PIXANO_INFERENCE_URL", "address of the pixano-inference server"),
            inference_api_key=os.environ.get("PIXANO_INFERENCE_API_KEY", ""),
            library_dir=_required("PIXANO_LIBRARY_DIR", "directory of the LanceDB library"),
            media_root=_required("PIXANO_MEDIA_ROOT", "media root as seen by the worker"),
            inference_media_root=_required("PIXANO_INFERENCE_MEDIA_ROOT", "media root as seen by the inference"),
            heartbeat_path=heartbeat_path(),
            concurrency=_positive("PIXANO_WORKER_CONCURRENCY", DEFAULT_CONCURRENCY, int),
            chunk_timeout_s=_positive("PIXANO_WORKER_CHUNK_TIMEOUT_S", DEFAULT_CHUNK_TIMEOUT_S, float),
            demo_kinds=_flag(DEMO_KINDS_FLAG),
        )

    def describe(self) -> str:
        """Make the configuration readable in the logs, without disclosing any secret."""
        lines = [
            f"  database          : {redact_dsn(self.database_url)}",
            f"  inference         : {self.inference_url}"
            + (" (authenticated)" if self.inference_api_key else " (no API key)"),
            f"  library           : {self.library_dir}",
            f"  media (worker)    : {self.media_root}",
            f"  media (inference) : {self.inference_media_root}",
            f"  concurrency       : {self.concurrency} chunk(s) at a time",
            f"  demo kinds        : {'enabled' if self.demo_kinds else 'disabled'}",
            f"  chunk time limit  : {self.chunk_timeout_s:g} s",
        ]
        return "\n".join(lines)
