# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Whether the app is alive, and whether it can serve: two questions, answered apart.

`GET /health/live` says that the process answers, and tests nothing else: what restarts a process
must not restart it because a database is down. `GET /health/ready` tests what the app depends on —
the storage of the library, then PostgreSQL where the deployment configured it — and answers 503,
naming what is missing, until all of it is there. Nothing is remembered from one call to the next:
the app is ready again as soon as what was missing is back.

The inference is asked too, and fails nothing: the app serves everything that needs no model
without it. An inference that does not answer is named under `degraded`, and the app stays ready.

`GET /health`, in `pixano.api.main`, stays what it was for the probes that call it: it tests
nothing.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Annotated, Awaitable, Callable, Literal

import boto3
import psycopg
from botocore.config import Config
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from s3path import S3Path

from pixano.api.settings import Settings, get_settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])

CHECK_TIMEOUT_S = 2.0
"""How long a dependency is given to answer before it counts as missing. The dependencies are
asked at once, so the readiness takes no longer than that to say what is missing, whatever a
dependency is stuck in. A probe that reads the answer, and not only whether one came, waits a
little longer."""

CLIENT_TIMEOUT_S = 2
"""The timeout handed to the clients that take one — PostgreSQL's connection, S3's connection and
read. It ends the thread of a check the readiness gave up on. psycopg takes no less than 2 s."""

OPTIONAL_CHECK_TIMEOUT_S = 0.5
"""How long a dependency the app serves without — the inference — is given to answer. It fails
nothing, so it must not hold the answer either: a probe that waits one second, as Kubernetes does
unless told otherwise, still gets its answer while the inference hangs."""

PROBE_THREADS = 4
"""How many checks of one dependency run at once, for the probes that call at the same moment."""

# The threads the blocking checks run in, a few per dependency and none shared with the data routes:
# in the pool those fill, a check would wait for a thread past its time, and the readiness would
# name a dependency that answers. A check that hangs — a stale network mount, a name that does not
# resolve — keeps its thread until it ends, and no other: once a dependency holds all of its own,
# the next calls find it silent without starting one more, and the other dependency is still asked.
_STORAGE_THREADS = ThreadPoolExecutor(max_workers=PROBE_THREADS, thread_name_prefix="pixano-ready-storage")
_POSTGRESQL_THREADS = ThreadPoolExecutor(max_workers=PROBE_THREADS, thread_name_prefix="pixano-ready-postgresql")

# What a check that failed tells a client. The error itself goes to the log: a database's can name
# its host, its user, even a password in a mistyped URL, and this route is open to every probe.
LOG_SAYS_WHY = "the log of the app says why"
LIBRARY_DIRECTORY_MISSING = "the library directory is missing or cannot be reached"
LIBRARY_BUCKET_UNREACHABLE = f"the bucket of the library cannot be reached — {LOG_SAYS_WHY}"
POSTGRESQL_UNREACHABLE = f"PostgreSQL accepted no connection — {LOG_SAYS_WHY}"
INFERENCE_UNREACHABLE = f"the default inference provider could not list its models — {LOG_SAYS_WHY}"


class LivenessResponse(BaseModel):
    """The process answers.

    Attributes:
        status: Always `ok`: a process that is not alive does not answer.
    """

    status: Literal["ok"] = "ok"


class DependencyCheck(BaseModel):
    """What one dependency of the app answered.

    Attributes:
        status: `ok` when it answered, `unavailable` when it did not, `not_configured` when the
            deployment does not use it — which is no failure.
        detail: Why it is unavailable, for an operator to read; None otherwise.
    """

    status: Literal["ok", "unavailable", "not_configured"]
    detail: str | None = None


class ReadinessChecks(BaseModel):
    """Each dependency of the app, by name.

    Attributes:
        storage: The library: a local directory that exists, or an S3 bucket that answers.
        postgresql: The database of the job queue, where `PIXANO_DATABASE_URL` names one.
        inference: The default inference provider, where one is connected. The app serves without
            it: it is reported, and never makes the app not ready.
    """

    storage: DependencyCheck
    postgresql: DependencyCheck
    inference: DependencyCheck


class ReadinessResponse(BaseModel):
    """Whether the app can serve.

    Attributes:
        status: `ok` when the app can serve: the storage answered, and PostgreSQL where it is
            configured. `unavailable` otherwise.
        missing: The names of the dependencies the app cannot serve without and that did not
            answer, as `checks` names them. Empty when the app is ready.
        degraded: The names of the dependencies that did not answer and that the app serves
            without: what needs them fails, and nothing else. Today, the inference.
        checks: What each dependency answered.
    """

    status: Literal["ok", "unavailable"]
    missing: list[str]
    degraded: list[str]
    checks: ReadinessChecks


async def _checked(
    name: str, probe: Callable[[], Awaitable[object]], failed: str, *, optional: bool = False
) -> DependencyCheck:
    """What a dependency answers to its probe, within the time a check is given.

    An optional dependency is one the app serves without. It is given less time, and the log says
    `degraded` where it says `not ready` for the others.
    """
    timeout = OPTIONAL_CHECK_TIMEOUT_S if optional else CHECK_TIMEOUT_S
    consequence = "degraded" if optional else "not ready"
    try:
        await asyncio.wait_for(probe(), timeout)
    except asyncio.TimeoutError:
        logger.warning("%s: %s gave no answer within %g s", consequence, name, timeout)
        return DependencyCheck(status="unavailable", detail=f"no answer within {timeout:g} s")
    except Exception as error:  # noqa: BLE001 - whatever a dependency fails with, it is missing
        logger.warning("%s: %s: %s: %s", consequence, name, type(error).__name__, error)
        return DependencyCheck(status="unavailable", detail=failed)
    return DependencyCheck(status="ok")


def _in_thread(
    threads: ThreadPoolExecutor, probe: Callable[..., object], *args: object
) -> Callable[[], Awaitable[object]]:
    """A blocking probe, to run off the event loop, in a thread of its dependency.

    The thread is left to end on its own when the readiness gives up on it: waiting for it would
    hold the answer for as long as the dependency hangs.
    """
    return lambda: asyncio.get_running_loop().run_in_executor(threads, partial(probe, *args))


def _library_directory_exists(library_dir: Path) -> None:
    if not library_dir.is_dir():
        raise NotADirectoryError(f"{library_dir} is not a directory")


def _library_bucket_answers(settings: Settings, library_dir: S3Path) -> None:
    """Ask S3 for the bucket of the library: one `HeadBucket`, the cheapest call it must answer.

    A prefix that holds no object does not exist on S3, so an empty library has nothing to ask for
    under its own key: the bucket answering to the app's credentials is what proves the storage.
    The client is made for the call, with the app's credentials and short timeouts: boto3's defaults
    wait a minute for a connection, then try again.
    """
    client = boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key,
        aws_secret_access_key=settings.aws_secret_key,
        config=Config(
            connect_timeout=CLIENT_TIMEOUT_S, read_timeout=CLIENT_TIMEOUT_S, retries={"total_max_attempts": 1}
        ),
    )
    client.head_bucket(Bucket=library_dir.bucket)


def _postgresql_accepts_a_connection(database_url: str) -> None:
    """Open a connection and close it: the server is up, and knows the database and the role.

    Whether the worker installed the queue is not asked: the app serves everything but the jobs
    without it, and the job routes say so themselves. The timeout replaces the URL's own, if any.
    """
    psycopg.connect(database_url, connect_timeout=CLIENT_TIMEOUT_S).close()


async def _storage(settings: Settings) -> DependencyCheck:
    library_dir = settings.library_dir
    if isinstance(library_dir, S3Path):
        probe = _in_thread(_STORAGE_THREADS, _library_bucket_answers, settings, library_dir)
        return await _checked("the storage", probe, LIBRARY_BUCKET_UNREACHABLE)
    probe = _in_thread(_STORAGE_THREADS, _library_directory_exists, library_dir)
    return await _checked("the storage", probe, LIBRARY_DIRECTORY_MISSING)


async def _postgresql(settings: Settings) -> DependencyCheck:
    database_url = settings.database_url
    if not database_url:
        return DependencyCheck(status="not_configured")
    probe = _in_thread(_POSTGRESQL_THREADS, _postgresql_accepts_a_connection, database_url)
    return await _checked("PostgreSQL", probe, POSTGRESQL_UNREACHABLE)


async def _inference(settings: Settings) -> DependencyCheck:
    """Ask the default provider for its models: the one call every provider answers.

    The default provider is the one the inference routes use when a request names none. The app
    serves without it, so the check is optional: it is reported, and decides nothing.
    """
    name = settings.default_inference_provider
    provider = settings.inference_providers.get(name) if name else None
    if provider is None:
        return DependencyCheck(status="not_configured")
    return await _checked(
        f"the inference provider {name}", lambda: provider.list_models(), INFERENCE_UNREACHABLE, optional=True
    )


def _did_not_answer(check: DependencyCheck) -> bool:
    return check.status == "unavailable"


@router.get("/live", operation_id="health_live")
async def health_live() -> LivenessResponse:
    """Tell that the process is alive. It tests nothing else.

    Answered on the event loop, without a thread of the pool the data routes share: it answers
    as long as the loop turns, however busy the app is.
    """
    return LivenessResponse()


@router.get(
    "/ready",
    operation_id="health_ready",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "A dependency the app cannot serve without did not answer: `missing` names it.",
        }
    },
)
async def health_ready(settings: Annotated[Settings, Depends(get_settings)], response: Response) -> ReadinessResponse:
    """Tell whether the app can serve: test what it depends on, and name what is missing.

    The storage of the library is always tested, and PostgreSQL where the deployment configured it:
    not configured, it is reported so and fails nothing. The inference is asked too, where the app
    is connected to one, and never fails the readiness: the app serves everything that needs no
    model without it. An inference that does not answer is named under `degraded`.
    """
    storage, postgresql, inference = await asyncio.gather(
        _storage(settings), _postgresql(settings), _inference(settings)
    )
    checks = ReadinessChecks(storage=storage, postgresql=postgresql, inference=inference)
    missing = [name for name, check in (("storage", storage), ("postgresql", postgresql)) if _did_not_answer(check)]
    degraded = ["inference"] if _did_not_answer(inference) else []
    if missing:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="unavailable" if missing else "ok", missing=missing, degraded=degraded, checks=checks
    )
