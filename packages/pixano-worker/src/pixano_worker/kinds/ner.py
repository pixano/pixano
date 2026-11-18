# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The named entity recognition job kind: the mentions a model finds in a dataset's texts.

Each text view is sent on its own — the inference's NER endpoint takes one text per call — and
every entity the model recognizes, of the classes asked for and scored enough, comes back as a
pre-annotation: a text span in the text spans table, its mention and its offsets in the text, and
the object it designates in the entities table, its class — the entity's label, a person, a place
— in the field `JobWriter.ensure_label_field` chooses.

A person's work is never contradicted. A span someone marked or accepted — an edit accepts a
model's span — is left alone by a rerun, and a mention that overlaps such a span, whatever its
class, is not written: a stretch of text holds one entity, and the person has already said which.
A span someone deleted is gone: nothing keeps the model from proposing it again.

Offsets are stored as the interface counts them, in UTF-16 code units, the end left out; the
model's are taken as Python counts a text's characters, in code points. The two differ past the
first character outside the Basic Multilingual Plane — U+1F389, an emoji —, so each mention is converted.

No person can review a text span yet (`pixano.schemas.is_reviewable_annotation`): the spans a
model proposes stay out of the review queue, and a person edits or deletes them as any other.
"""

import io
import logging
import time
from typing import Any, Callable, Iterable

import httpx
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_inference.schemas import NERRequest
from pydantic import Field

from pixano.inference.types import TASK_TO_CAPABILITY, InferenceTask
from pixano.schemas import DEFAULT_LABEL_FIELD, label_field_of
from pixano.utils.python import to_sql_list

from ..media import REMOTE_SCHEMES
from ..reader import JobReader, MediaType
from ..writer import ENTITY_TABLE, MODEL_SOURCE, Coverage, JobWriter, ModelIdentity, is_a_persons_work
from .base import (
    CONFIRM_MARKER,
    MODEL_TASK_MARKER,
    Chunk,
    JobKind,
    JobParams,
    Outcome,
    QuarantinedItem,
    TransientError,
    media_chunks,
)
from .inference import (
    MEDIA_NOT_FOUND,
    REFUSED_BY_THE_SERVER,
    InferenceServer,
    classify,
    quarantined_item,
    refusal_detail,
    refuse_unless_the_witness_passes,
)


log = logging.getLogger("pixano-worker")

# The task of the model this kind calls, in Pixano's vocabulary and in pixano-inference's.
NER_TASK = InferenceTask.NER
NER_CAPABILITY = TASK_TO_CAPABILITY[NER_TASK]

# The media this kind reads: the text views, whose content is sent as it is.
TEXT_MEDIA = "text"

# The annotation slot, and its canonical table, of the spans this kind writes.
TEXT_SPAN_SLOT = "text_span"

# A text any NER model reads: sent when the server refused every text of a chunk, to tell a server
# that is not well from texts it cannot read.
WITNESS_TEXT = "Ada Lovelace was born in London."

# Why a text held by a URI alone goes to quarantine without a call: it lives at a URL — the
# importer keeps a text at an HTTP or S3 address so —, which this worker does not fetch; its file is
# not under the media root, or cannot be read there; or it is not UTF-8.
TEXT_NOT_HELD = "text stored at a URL this worker does not read"
TEXT_FILE_NOT_FOUND = "text file not found under the media root"
TEXT_FILE_UNREADABLE = "text file unreadable"
TEXT_NOT_UTF8 = "text file not UTF-8"

# A chunk's cost is its calls, one per text, made one after another. A model that answers slowly
# costs at most the call's timeout for each text: sixteen texts of a minute each take sixteen
# minutes. A call that does not answer is replayed by the client (`max_retries`), then hands the
# chunk back: four minutes more with the defaults. Both stay within the worker's time limit of a
# chunk (`DEFAULT_CHUNK_TIMEOUT_S`, thirty minutes); a larger chunk or a longer timeout may not,
# and the chunk is then taken for hung and replayed (backend-processing §25.1).
DEFAULT_CHUNK_SIZE = 16
MAX_CHUNK_SIZE = 256
DEFAULT_REQUEST_TIMEOUT_S = 60.0
# Short retries of a call that failed transiently, done by the inference client, as the other kinds.
DEFAULT_MAX_RETRIES = 3
MAX_RETRIES = 10
# A model that gives no score answers 1.0: half keeps what a model is at least as sure of as not.
DEFAULT_SCORE_THRESHOLD = 0.5

# The last code point of the Basic Multilingual Plane: a character past it takes two UTF-16 code
# units, one before it, one.
BMP_LAST_CODE_POINT = 0xFFFF
SURROGATE_PAIR_UNITS = 2


class NerParams(JobParams):
    """Parameters of the named entity recognition job.

    Attributes:
        model: The model name as the inference declares it.
        media: The media types to run the model on. Only texts can be sent; another type refuses
            the whole job.
        entity_types: The classes to keep — `PER`, `LOC`, as the model names them, case aside.
            Empty, every class the model returns. A job with classes replaces only the spans of
            those classes: asking for places, then for people, keeps the places.
        score_threshold: The score below which a recognized entity is not written.
        replace_previous: Delete, before recognizing, every span this kind wrote that is still to
            review, whatever its model — of the classes asked for, when there are some. A span a
            person accepted stays, and so does one whose object a person worked on. Without it, a
            rerun of the same model replaces its own spans and another model's stay. Done once, at
            planning; the form asks for confirmation.
        chunk_size: Texts per chunk — as many calls to the inference, one per text.
        max_retries: Short retries of a call that failed transiently, done by the inference client
            before handing back. Beyond that, the chunk is handed back to the queue.
        request_timeout_s: Beyond this, a call is considered lost.
    """

    # No default: the model is whichever the inference serves for NER, which the form offers.
    model: str = Field(min_length=1, json_schema_extra={MODEL_TASK_MARKER: NER_TASK.value})
    # A plain default rather than a factory, so that pydantic publishes it and the form starts from it.
    media: list[MediaType] = Field(default=[TEXT_MEDIA], min_length=1)
    entity_types: list[str] = Field(
        default=[],
        description="The classes to keep, as the model names them (PER, LOC, ORG); empty: every class it returns.",
    )
    score_threshold: float = Field(
        default=DEFAULT_SCORE_THRESHOLD,
        ge=0,
        le=1,
        description="The score below which a recognized entity is not written.",
    )
    replace_previous: bool = Field(
        default=False,
        json_schema_extra={
            CONFIRM_MARKER: "This deletes the text spans every NER job wrote on this dataset that are still to "
            "review — only those of the classes asked for, if you set some — before recognizing again. A span "
            "a person accepted, or whose object a person worked on, stays."
        },
    )
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, ge=1, le=MAX_CHUNK_SIZE)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=0, le=MAX_RETRIES)
    request_timeout_s: float = Field(default=DEFAULT_REQUEST_TIMEOUT_S, gt=0)


class NerKind(JobKind[NerParams]):
    """Proposes the named entities of a dataset's texts, and the objects they designate."""

    name = "ner"
    params_model = NerParams
    # The inference's NER endpoint takes a text.
    supported_media = frozenset({TEXT_MEDIA})
    # A recognized entity is the output of a model, and arrives as a model's proposal.
    source_type = MODEL_SOURCE

    #: How the engine runs the job, not what it computes: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {
        "request_timeout_s",
        "max_retries",
        # What the job did to the dataset before recognizing, not how an entity was found.
        "replace_previous",
    }

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Bind this kind to the inference server the worker knows."""
        self.server = InferenceServer(inference_url, api_key)

    def model_identity(self, params: NerParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it."""
        return self.server.model_identity(params.model)

    def prepare(self, writer: JobWriter, params: NerParams) -> None:
        """Give the dataset a table of text spans and its entities a field for their class, and clear
        the spans still to review when asked.

        Each is idempotent: the table and the field are added once, and a second clearing finds
        nothing left. Destructive only on the explicit parameter, as the contract requires.
        """
        table = writer.ensure_table(TEXT_SPAN_SLOT)
        field = writer.ensure_label_field()
        if params.replace_previous:
            writer.drop_pending(table, with_entities=True, covers=_types_covered(params.entity_types, field))

    def plan(self, reader: JobReader, params: NerParams) -> Iterable[Chunk]:
        """Split the dataset's texts into batches, after checking the job can run at all.

        Raises:
            ValueError: A chosen media type cannot be processed, the dataset has no text, no table
                to hold the objects a mention designates nor a field to hold their class, or the
                inference serves no such model.
        """
        self.refuse_unsupported_media(params.media)
        tables = reader.dataset.info.tables
        if not reader.media_tables(TEXT_MEDIA):
            raise ValueError("this dataset has no text to recognize entities in")
        if ENTITY_TABLE not in tables:
            raise ValueError(f"this dataset has no '{ENTITY_TABLE}' table to write the recognized entities into")
        entity = tables[ENTITY_TABLE]
        if label_field_of(entity) is None and DEFAULT_LABEL_FIELD in getattr(entity, "model_fields", {}):
            # The field a class would be added as exists with another type: every write would
            # fail on it, chunk after chunk. Said once, here.
            raise ValueError(
                f"this dataset's entities have a '{DEFAULT_LABEL_FIELD}' field that is not text, and no text field "
                "to hold the class of a recognized entity"
            )
        self.server.require_served(params.model, NER_CAPABILITY)
        yield from media_chunks(reader, params.media, params.chunk_size)

    def process(self, reader: JobReader, payload: dict[str, Any], params: NerParams) -> dict[str, Any]:
        """Recognize the entities of each text of a batch, and return them, with the fate of each text.

        A text that cannot be found, or that the inference refuses, goes to **quarantine**, its
        record in the detail. So does a text held by a URI alone, without its content, whose file
        this worker cannot read: at a URL, missing from the media root, unreadable, or not UTF-8 —
        it is read from its file otherwise. An empty text, or one of blanks alone, has nothing to
        recognize: it is **skipped**. Otherwise it is **produced**, even with no entity: a text
        where the model finds none is an answer.

        A server that refuses every text of a chunk is sent a witness text: refusing it too, the
        server is at fault, not the texts, and the chunk is replayed later.

        The calls are made one after another: the chunk says how far it got after each, and stops
        before the next once its job is cancelled.

        Raises:
            TransientError: The inference does not answer, asks to come back later, or refuses
                even the witness text.
            ChunkCancelled: The job was cancelled while the chunk ran.
        """
        table: str = payload["table"]
        view_ids: list[str] = payload["view_ids"]
        started = time.perf_counter()
        views = {row.id: row for row in reader.rows(table, view_ids)} if view_ids else {}
        quarantined: list[dict[str, Any]] = []
        contents: list[tuple[Any, str]] = []
        skipped = 0
        for view_id in view_ids:
            view = views.get(view_id)
            if view is None:
                quarantined.append(quarantined_item(view_id, MEDIA_NOT_FOUND))
                continue
            content, reason = _content_of(reader, table, view)
            if reason is not None:
                quarantined.append(quarantined_item(view.id, reason, view.record_id))
            elif not content.strip():
                skipped += 1
            else:
                contents.append((view, content))
        read_s = time.perf_counter() - started

        texts: list[dict[str, Any]] = []
        refused: list[tuple[Any, dict[str, Any]]] = []
        # Closed with the chunk: a client holds a connection pool, and a worker runs thousands of chunks.
        with self.server.client(max_retries=params.max_retries) as client:
            started = time.perf_counter()
            # The texts settled without a call are done already: each call answered adds one.
            settled = len(view_ids) - len(contents)
            for done, (view, content) in enumerate(contents, start=settled + 1):
                reader.progress.stop_if_cancelled()
                try:
                    output = self._recognize(client, content, params)
                except (httpx.TransportError, PixanoInferenceError) as error:
                    failure = classify(error)
                    if failure == "transient":
                        raise TransientError(
                            f"the inference does not answer or asks to come back later: {error}"
                        ) from error
                    if failure == "request":
                        raise
                    refused.append((view, refusal_detail(error)))  # type: ignore[arg-type]
                else:
                    texts.append(
                        {
                            "view_id": view.id,
                            "record_id": view.record_id,
                            "mentions": _kept_mentions(output.entities, content, params),
                        }
                    )
                reader.progress.advance_to(done)
            inference_s = time.perf_counter() - started
            if refused and not texts:
                refuse_unless_the_witness_passes(
                    lambda text: self._recognize(client, text, params), WITNESS_TEXT, "text"
                )
        quarantined.extend(
            quarantined_item(view.id, REFUSED_BY_THE_SERVER, view.record_id, **detail) for view, detail in refused
        )
        return {
            "texts": texts,
            "skipped": skipped,
            "quarantined": quarantined,
            "phases_s": {"read": read_s, "inference": inference_s},
        }

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """What `process` observed for each text."""
        return Outcome(
            produced=len(result["texts"]),
            skipped=result["skipped"],
            quarantined=[QuarantinedItem.model_validate(item) for item in result["quarantined"]],
        )

    def write(self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: NerParams) -> None:
        """Write each text's spans and their objects, replacing what the same model wrote there.

        With classes asked for, only the spans of those classes are replaced: the others the same
        model wrote there stay. A mention that overlaps a span a person marked or accepted, whatever
        its class, is dropped: that span already says what is there. So is one over a model's span
        whose object a person worked on, which the writer keeps (`_protected_ranges`).
        """
        started = time.perf_counter()
        # Again here and not only at planning: a worker whose dataset was opened before the table
        # or the field was added still holds the schema without it.
        table = writer.ensure_table(TEXT_SPAN_SLOT)
        field = writer.ensure_label_field()
        span_schema = writer.table_schema(table)
        entity_schema = writer.table_schema(ENTITY_TABLE)
        provenance = writer.provenance()
        scope = _types_covered(params.entity_types, field)
        protected = _protected_ranges(writer, table, [text["view_id"] for text in result["texts"]])
        written = dropped = 0
        for text in result["texts"]:
            spans, entities = [], []
            for mention in text["mentions"]:
                if _overlaps_any(mention, protected.get(text["view_id"], [])):
                    dropped += 1
                    continue
                spans.append(
                    span_schema(
                        id="",
                        record_id=text["record_id"],
                        view_id=text["view_id"],
                        mention=mention["text"],
                        spans_start=[mention["start"]],
                        spans_end=[mention["end"]],
                        **provenance,
                    )
                )
                entities.append(entity_schema(id="", record_id=text["record_id"], **{field: mention["label"]}))
            written += len(writer.replace(table, text["view_id"], spans, entities, covers=scope))
        phases = result.get("phases_s", {})
        log.info(
            "job %s: phases read %.3f s, inference %.3f s, write %.3f s (%d span(s), %d left to a person's span)",
            writer.job_id,
            phases.get("read", 0.0),
            phases.get("inference", 0.0),
            time.perf_counter() - started,
            written,
            dropped,
        )

    @staticmethod
    def _recognize(client: SyncPixanoInferenceClient, content: str, params: NerParams) -> Any:
        """One recognition call, on one text."""
        request = NERRequest(model=params.model, text=content)
        return client.ner(request, timeout=params.request_timeout_s).data


def _content_of(reader: JobReader, table: str, view: Any) -> tuple[str, str | None]:
    """A text view's content, and why it cannot be read, if it cannot.

    Its content as the dataset holds it; else, for a text held by a URI alone, the file this worker
    reaches — the importer reads a local file into the content, so only a dataset built otherwise
    has one. The file is read as the importer reads one, its line ends made line feeds, so that
    offsets found on it hold on the content an import would give. A text at a URL — HTTP, S3 — is not
    fetched: it is no text this worker holds.
    """
    content = str(getattr(view, "content", "") or "")
    uri = str(getattr(view, "uri", "") or "")
    if content or not uri:
        return content, None
    try:
        media = reader.open_media(table, view)
        if media is None:
            return "", TEXT_NOT_HELD if uri.startswith(REMOTE_SCHEMES) else TEXT_FILE_NOT_FOUND
        with io.TextIOWrapper(media, encoding="utf-8") as text:
            return text.read(), None
    except UnicodeDecodeError:
        return "", TEXT_NOT_UTF8
    # A file this worker sees but cannot read is the text's failure, not the chunk's.
    except OSError as error:
        log.warning("text %s: cannot read its file (%s)", view.id, error)
        return "", TEXT_FILE_UNREADABLE


def _to_utf16(content: str) -> Callable[[int], int]:
    """Where each character of a text stands in UTF-16 code units, as the interface counts.

    The same index while every character is in the Basic Multilingual Plane — the usual text —;
    else read from a table of the text's positions, built once.
    """
    if max(map(ord, content), default=0) <= BMP_LAST_CODE_POINT:
        return lambda index: index
    positions = [0]
    for character in content:
        positions.append(positions[-1] + (SURROGATE_PAIR_UNITS if ord(character) > BMP_LAST_CODE_POINT else 1))
    return positions.__getitem__


def _kept_mentions(entities: Iterable[Any], content: str, params: NerParams) -> list[dict[str, Any]]:
    """The entities to write: of the classes asked for, scored enough, placed within the text, once each.

    A mention's text is the text's own between its offsets, whatever text the model says it found;
    offsets out of the text, or empty, place nothing, and are left out. The offsets kept are counted
    in UTF-16 code units (module docstring). A mention the model returns twice, same class and same
    place, is kept once.
    """
    wanted = {name.casefold() for name in params.entity_types}
    to_utf16 = _to_utf16(content)
    kept: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for entity in entities:
        label = str(entity.label or "")
        if wanted and label.casefold() not in wanted:
            continue
        if entity.score < params.score_threshold:
            continue
        start, end = int(entity.start), int(entity.end)
        if not 0 <= start < end <= len(content):
            continue
        place = (to_utf16(start), to_utf16(end), label)
        if place in seen:
            continue
        seen.add(place)
        kept.append({"text": content[start:end], "label": label, "start": place[0], "end": place[1]})
    return kept


def _types_covered(entity_types: list[str], field: str) -> Coverage | None:
    """The previous spans a job asked for these classes is about: those of its classes, case aside.
    None — every span — when it asked for none.
    """
    if not entity_types:
        return None
    wanted = {name.casefold() for name in entity_types}
    return lambda _span, entity: str(getattr(entity, field, "") or "").casefold() in wanted


def _protected_ranges(writer: JobWriter, table: str, view_ids: list[str]) -> dict[str, list[tuple[int, int]]]:
    """The ranges of these texts a recognition must not contradict, by text, read once for a chunk.

    A span a person marked — anything but a model's output — or one a person accepted. And a model's
    span nobody reviewed whose object carries a person's work elsewhere: the writer keeps that object
    at its rank, so the span stays, and proposing the entity again would put a second span on it.
    An empty range protects nothing: it covers no character.
    """
    if not view_ids:
        return {}
    rows = writer.read(table, f"view_id IN {to_sql_list(view_ids)}")
    unreviewed = {row.entity_id for row in rows if row.entity_id and not is_a_persons_work(row)}
    held = writer.entities_with_a_persons_work(unreviewed, table) if unreviewed else set()
    ranges: dict[str, list[tuple[int, int]]] = {}
    for row in rows:
        if not (is_a_persons_work(row) or row.entity_id in held):
            continue
        for start, end in zip(row.spans_start, row.spans_end, strict=True):
            if start < end:
                ranges.setdefault(row.view_id, []).append((start, end))
    return ranges


def _overlaps_any(mention: dict[str, Any], protected: list[tuple[int, int]]) -> bool:
    """Whether a mention shares a character with a protected range."""
    return any(mention["start"] < end and start < mention["end"] for start, end in protected)
