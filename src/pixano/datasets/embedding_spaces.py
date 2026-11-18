# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset's embedding spaces: one table of vectors per model, and the model a search uses by default.

Each model gets its own LanceDB table, with its own dimension, metric and vector index: a job of
one model never rewrites the rows another model's index covers, and two models' jobs never write
the same table (backend-processing §12). A dataset describes its spaces in `embeddings.json`, beside
`info.json`, and names the one a search uses when none is named:

    {"version": 2, "default": "clip-3f2a9c1d", "spaces": [{"id": "clip-3f2a9c1d",
     "table": "embeddings_clip-3f2a9c1d", "model_id": "clip", "checkpoint": "MobileCLIP2-S2", "dim": 512,
     "metric": "cosine", "source_view": "image", "index_type": "IVF_SQ"}, ...]}

A model is its name and its checkpoint: two checkpoints of one name are two spaces, their vectors not
comparable. A space or a caller that does not say its checkpoint — a space recorded before
checkpoints were, an inference that could not tell — is that name's, unless their dimensions differ,
which proves two models. A new space's table is `embeddings_<id>`.

The document a dataset wrote before there were several models — one model's fields at its top
level, its vectors in the table `embeddings` — is read as that one space, which keeps its table, and
is written in this format at its first change.

What a document holds that this build does not know — a field of a later version — is written back
as it was read. A document this build cannot read entirely is not to be rewritten at all
(`EmbeddingSpaces.fully_read`): what it would leave out is vectors no description names any more.

This module only reads and writes the description; `Dataset` keeps the tables.
"""

import hashlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any


logger = logging.getLogger(__name__)

#: The version of the document this module writes, and the latest it reads.
FORMAT_VERSION = 2
#: The table of the one model a dataset described before there were several: its space keeps it.
LEGACY_TABLE = "embeddings"
#: What names a space's table, before the space's id.
TABLE_PREFIX = "embeddings_"
#: The longest part of a model's name a space's id keeps.
_MAX_SLUG_LENGTH = 40
#: The hexadecimal digits of the hash that tells two checkpoints of one name apart.
_HASH_LENGTH = 8
#: The widest vector a table holds: Arrow's longest fixed-size list.
_MAX_DIM = 2**31 - 1

DEFAULT_METRIC = "cosine"
DEFAULT_SOURCE_VIEW = "image"
DEFAULT_INDEX_TYPE = "IVF_PQ"

#: The fields of a space this module reads; any other is written back as it was read.
_SPACE_FIELDS = frozenset({"id", "table", "model_id", "checkpoint", "dim", "metric", "source_view", "index_type"})
#: The fields of the document this module reads; any other is written back as read.
_DOCUMENT_FIELDS = frozenset({"version", "default", "spaces"})


class AmbiguousModelError(ValueError):
    """A writer that does not tell its model's checkpoint names several spaces of that model.

    Its vectors cannot go to one of them by guess: they would mix with another checkpoint's, which
    a search could not tell apart.
    """


def space_id(model_id: str, checkpoint: str) -> str:
    """The identifier of a model's space: its name made readable, and a hash of its name and checkpoint.

    Fixed once the space exists: a space recorded without a checkpoint keeps its id when it learns it.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", model_id.lower())[:_MAX_SLUG_LENGTH].strip("-") or "model"
    digest = hashlib.sha256(f"{model_id}\n{checkpoint}".encode()).hexdigest()[:_HASH_LENGTH]
    return f"{slug}-{digest}"


def is_embeddings_table(name: str) -> bool:
    """Whether a table's name is that of a space's table: `TABLE_PREFIX` and an id, or `LEGACY_TABLE`."""
    return name == LEGACY_TABLE or name.startswith(TABLE_PREFIX)


@dataclass(frozen=True)
class EmbeddingSpace:
    """One model's embeddings in a dataset.

    Attributes:
        id: The space's identifier, `space_id` of its model when it was created.
        table: The LanceDB table holding its vectors: `TABLE_PREFIX` and its id, or `LEGACY_TABLE`.
        model_id: The model's name, as the inference serves it.
        checkpoint: The weights loaded under that name; empty when the space was recorded without it.
        dim: The vectors' dimension.
        metric: The distance a search ranks them by.
        source_view: The views the vectors were computed from.
        index_type: The vector index the table gets once it holds enough vectors.
        unknown: What the space's entry holds that this build does not read, written back as it was.
    """

    id: str
    table: str
    model_id: str
    checkpoint: str
    dim: int
    metric: str = DEFAULT_METRIC
    source_view: str = DEFAULT_SOURCE_VIEW
    index_type: str = DEFAULT_INDEX_TYPE
    unknown: Mapping[str, Any] = field(default_factory=dict, hash=False)

    def as_document(self) -> dict[str, Any]:
        """The space as `embeddings.json` holds it."""
        return {
            **self.unknown,
            "id": self.id,
            "table": self.table,
            "model_id": self.model_id,
            "checkpoint": self.checkpoint,
            "dim": self.dim,
            "metric": self.metric,
            "source_view": self.source_view,
            "index_type": self.index_type,
        }

    def is_model(self, model_id: str, checkpoint: str, dim: int | None = None) -> bool:
        """Whether this space holds that model's vectors.

        The same name and checkpoint. A space or a request that does not say its checkpoint is that
        name's, unless the dimension the request gives is not the space's: two models.
        """
        if self.model_id != model_id:
            return False
        if self.checkpoint and checkpoint:
            return self.checkpoint == checkpoint
        return dim is None or self.dim == dim


def _space_from(entry: Any, *, flat: bool = False) -> EmbeddingSpace:
    """A space read from an entry of the document, or from the document written before several models (`flat`).

    Raises:
        ValueError: The entry is not a space this module can read.
    """
    if not isinstance(entry, dict):
        raise ValueError("an embedding space is an object")
    try:
        dim = int(entry["dim"])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"an embedding space's dimension is a whole number, not {entry.get('dim')!r}") from error
    if not 0 < dim <= _MAX_DIM:
        raise ValueError(f"an embedding space's dimension is between 1 and {_MAX_DIM}, not {dim}")
    model_id = str(entry.get("model_id") or "")
    checkpoint = str(entry.get("checkpoint") or "")
    identifier = str(entry.get("id") or space_id(model_id, checkpoint))
    # The document written before several models: whatever it says, the build that wrote it wrote its
    # vectors in the table `embeddings`.
    table = LEGACY_TABLE if flat else str(entry.get("table") or "")
    if table not in (LEGACY_TABLE, f"{TABLE_PREFIX}{identifier}"):
        raise ValueError(f"the embedding space {identifier} names the table '{table}', which is not one of its own")
    return EmbeddingSpace(
        id=identifier,
        table=table,
        model_id=model_id,
        checkpoint=checkpoint,
        dim=dim,
        metric=str(entry.get("metric") or DEFAULT_METRIC),
        source_view=str(entry.get("source_view") or DEFAULT_SOURCE_VIEW),
        index_type=str(entry.get("index_type") or DEFAULT_INDEX_TYPE),
        unknown={key: value for key, value in entry.items() if key not in _SPACE_FIELDS},
    )


@dataclass(frozen=True)
class EmbeddingSpaces:
    """Every embedding space of a dataset, in the order they were created, and the default one.

    Attributes:
        spaces: The spaces; no two share an id or a table.
        default: The id of the space a search uses when none is named; None exactly when there is none.
        fully_read: Whether the document they were read from was read entirely. One that was not — a
            space this build cannot read, a later version — must not be rewritten: the spaces left out
            would be lost, and their tables with them.
        unknown: What the document holds that this build does not read, written back as it was.
    """

    spaces: tuple[EmbeddingSpace, ...] = ()
    default: str | None = None
    fully_read: bool = True
    unknown: Mapping[str, Any] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        """Refuse two spaces of one id or one table, and a default that is none of them.

        Raises:
            ValueError: The spaces are not a dataset's.
        """
        ids = [space.id for space in self.spaces]
        if len(set(ids)) != len(ids) or len({space.table for space in self.spaces}) != len(ids):
            raise ValueError(f"two embedding spaces share an id or a table: {ids}")
        if (self.default is None) != (not ids) or (self.default is not None and self.default not in ids):
            raise ValueError(f"the default embedding space {self.default!r} is none of {ids}")

    @classmethod
    def from_document(cls, document: Any) -> "EmbeddingSpaces":
        """The spaces `embeddings.json` describes, in either format.

        A space this build cannot read is left out and logged, the others kept, and the result is not
        `fully_read`; nor is that of a document of a later version. A default naming no space falls
        back on the first.

        Raises:
            ValueError: The document is no object, or one written before several models that cannot be read.
        """
        if not isinstance(document, dict):
            raise ValueError("embeddings.json holds an object")
        if "spaces" not in document:
            # The document written before several models: one model's fields at its top level.
            only = _space_from(document, flat=True)
            return cls(spaces=(only,), default=only.id)
        entries = document["spaces"]
        version = document.get("version")
        fully_read = isinstance(entries, list) and isinstance(version, int) and version <= FORMAT_VERSION
        if not fully_read:
            logger.warning("embeddings.json: version %r, which this build does not read entirely", version)
        spaces: list[EmbeddingSpace] = []
        for entry in entries if isinstance(entries, list) else []:
            try:
                space = _space_from(entry)
            except ValueError as error:
                logger.warning("embeddings.json: leaving out an embedding space this build cannot read: %s", error)
                fully_read = False
                continue
            if any(kept.id == space.id or kept.table == space.table for kept in spaces):
                logger.warning("embeddings.json: leaving out a second embedding space %s", space.id)
                fully_read = False
                continue
            spaces.append(space)
        ids = [space.id for space in spaces]
        default = document.get("default")
        return cls(
            spaces=tuple(spaces),
            default=default if default in ids else (ids[0] if ids else None),
            fully_read=fully_read,
            unknown={key: value for key, value in document.items() if key not in _DOCUMENT_FIELDS},
        )

    def to_document(self) -> dict[str, Any]:
        """The spaces as `embeddings.json` holds them."""
        return {
            **self.unknown,
            "version": FORMAT_VERSION,
            "default": self.default,
            "spaces": [space.as_document() for space in self.spaces],
        }

    def find(self, model: str | None = None) -> EmbeddingSpace | None:
        """The space a reader names: by its id, or by its model's name; the default one when none is named.

        A name several spaces share — two checkpoints of one model — names the default one if it is
        among them, else the first created. A writer names a space by its id (`get`).
        """
        if model is None or model == "":
            return self.get(self.default) if self.default is not None else None
        named = self.get(model)
        if named is not None:
            return named
        of_name = [space for space in self.spaces if space.model_id == model]
        if not of_name:
            return None
        return next((space for space in of_name if space.id == self.default), of_name[0])

    def get(self, identifier: str) -> EmbeddingSpace | None:
        """The space of this id."""
        return next((space for space in self.spaces if space.id == identifier), None)

    def matching(
        self, model_id: str, checkpoint: str, dim: int | None = None, *, strict: bool = False
    ) -> EmbeddingSpace | None:
        """The space of a model, by its name and checkpoint (`EmbeddingSpace.is_model`).

        Where several match — a request that does not say its checkpoint, a space recorded
        without its own — the one of that very checkpoint first; failing it, the default one, then
        the first created, for a reader; none for a writer (`strict`), which would mix its vectors
        with another checkpoint's.

        Raises:
            AmbiguousModelError: `strict`, and several spaces match none of them by its checkpoint.
        """
        candidates = [space for space in self.spaces if space.is_model(model_id, checkpoint, dim)]
        if not candidates:
            return None
        exact = [space for space in candidates if space.checkpoint == checkpoint]
        if exact:
            return exact[0]
        if strict and len(candidates) > 1:
            checkpoints = ", ".join(space.checkpoint or "none told" for space in candidates)
            if checkpoint:
                raise AmbiguousModelError(
                    f"model '{model_id}' of checkpoint '{checkpoint}' matches {len(candidates)} embedding spaces "
                    f"recorded without theirs (checkpoints {checkpoints}): which is its own cannot be told"
                )
            raise AmbiguousModelError(
                f"model '{model_id}' names {len(candidates)} embedding spaces, of the checkpoints {checkpoints}: "
                "its own checkpoint must be told to choose"
            )
        return next((space for space in candidates if space.id == self.default), candidates[0])

    def new_space(
        self,
        model_id: str,
        checkpoint: str,
        dim: int,
        metric: str = DEFAULT_METRIC,
        source_view: str = DEFAULT_SOURCE_VIEW,
        index_type: str = DEFAULT_INDEX_TYPE,
    ) -> EmbeddingSpace:
        """A space for a model this dataset does not hold yet, of an id and a table no space has.

        Its id is `space_id` of the model, a number added if a space has it already — one that learnt
        its checkpoint after it was created —, and its table `TABLE_PREFIX` and that id.
        """
        ids = {space.id for space in self.spaces}
        identifier = base = space_id(model_id, checkpoint)
        number = 1
        while identifier in ids:
            number += 1
            identifier = f"{base}-{number}"
        return EmbeddingSpace(
            id=identifier,
            table=f"{TABLE_PREFIX}{identifier}",
            model_id=model_id,
            checkpoint=checkpoint,
            dim=int(dim),
            metric=metric,
            source_view=source_view,
            index_type=index_type,
        )

    def with_space(self, space: EmbeddingSpace) -> "EmbeddingSpaces":
        """These spaces and a new one, added last; the default kept, or the new one when there was none.

        Raises:
            ValueError: A space has its id or its table already.
        """
        return replace(self, spaces=(*self.spaces, space), default=self.default or space.id)

    def with_checkpoint(self, space: EmbeddingSpace, checkpoint: str) -> "EmbeddingSpaces":
        """These spaces, `space` now knowing its checkpoint; its id, table and place unchanged."""
        return self.replacing(replace(space, checkpoint=checkpoint))

    def replacing(self, space: EmbeddingSpace) -> "EmbeddingSpaces":
        """These spaces, `space` in place of the one of its id: its place, and the default, unchanged.

        Raises:
            KeyError: No space has its id.
            ValueError: Another space has its table.
        """
        if self.get(space.id) is None:
            raise KeyError(space.id)
        return replace(self, spaces=tuple(space if kept.id == space.id else kept for kept in self.spaces))

    def without(self, identifier: str) -> "EmbeddingSpaces":
        """These spaces but the one of this id; the default moves to the first left if it was that one."""
        kept = tuple(space for space in self.spaces if space.id != identifier)
        default = self.default if self.default != identifier else (kept[0].id if kept else None)
        return replace(self, spaces=kept, default=default)

    def with_default(self, identifier: str) -> "EmbeddingSpaces":
        """These spaces, this one the default.

        Raises:
            KeyError: No space has this id.
        """
        if self.get(identifier) is None:
            raise KeyError(identifier)
        return replace(self, default=identifier)
