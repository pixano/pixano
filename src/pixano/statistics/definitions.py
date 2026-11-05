# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Statistics a person composes from fixed choices, and the rules that keep them meaningful.

A statistic is a value computed for each record, or for each object, of a dataset from its
annotations: how many boxes a record holds, the mean area of an object's masks. A person composes
it from fixed choices — never a formula, never code (backend-processing §22):

- the **level**: one value per record, or per object;
- the **element** measured: an annotation kind the dataset holds, or, per record, its objects;
- the **measure**: how many there are, or, for boxes and masks, their area in pixels or the share
  of the image they cover;
- the **aggregation** that brings several areas to one value: their mean, minimum, maximum or sum;
- optional **filters** on what counts: an attribute value of the object, the annotation's origin,
  its review status.

The column's name, unit and type follow from those choices: two people composing the same
statistic get the same column, and a column name says what it holds.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pixano.schemas import ReviewStatus, is_reviewable_annotation
from pixano.schemas.table_names import canonical_family_spec_for_slot


class StatisticLevel(Enum):
    """What a statistic gives one value for.

    Attributes:
        RECORD: Each record of the dataset.
        ENTITY: Each object of the dataset.
    """

    RECORD = "record"
    ENTITY = "entity"


class StatisticMeasure(Enum):
    """How a statistic measures its element.

    Attributes:
        COUNT: How many there are.
        AREA: Their area, in pixels.
        IMAGE_RATIO: The share of their image each covers, from 0 to 1. A sum of shares can pass 1,
            where annotations overlap or a record holds several images.
    """

    COUNT = "count"
    AREA = "area"
    IMAGE_RATIO = "image_ratio"


class StatisticAggregation(Enum):
    """How a statistic brings the areas of several annotations to one value.

    Attributes:
        MEAN: Their mean.
        MIN: The smallest.
        MAX: The largest.
        SUM: Their sum.
    """

    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    SUM = "sum"


class AnnotationOrigin(Enum):
    """Who made the annotations a statistic counts.

    Attributes:
        MODEL: A model's predictions (`source_type` "model").
        NOT_MODEL: Everything else: a person's annotations, and imported ones.
    """

    MODEL = "model"
    NOT_MODEL = "not_model"


#: The element that stands for the objects themselves, rather than an annotation kind.
ENTITY_ELEMENT = "entity"
#: The annotation kinds whose area a statistic measures, by their `DatasetInfo` slot.
BOX_ELEMENT = "bbox"
MASK_ELEMENT = "mask"

#: What a statistic can measure: the objects, or an annotation kind by its `DatasetInfo` slot. The
#: plural names it in a statistic's label.
ELEMENT_NAMES: dict[str, str] = {
    ENTITY_ELEMENT: "objects",
    BOX_ELEMENT: "boxes",
    "bbox3d": "3D boxes",
    MASK_ELEMENT: "masks",
    "keypoint": "keypoint sets",
    "multi_path": "lines",
    "text_span": "text spans",
    "classification": "classifications",
    "tracklet": "tracks",
}

#: The annotation kinds whose area a statistic measures: a box's, from its coordinates, and a mask's,
#: from its pixels.
ELEMENTS_WITH_AREA: frozenset[str] = frozenset({BOX_ELEMENT, MASK_ELEMENT})

#: The version of each measure's computation. A computation that changes gets the next version,
#: and its statistic a column of its own, rather than overwriting the values of the previous one
#: in silence.
MEASURE_VERSIONS: dict[StatisticMeasure, int] = {
    StatisticMeasure.COUNT: 1,
    StatisticMeasure.AREA: 1,
    StatisticMeasure.IMAGE_RATIO: 1,
}

#: The longest column name, in characters: PostgreSQL's limit on an identifier, the strictest of the
#: engines a statistic's column may meet (DuckDB, Arrow and Lance set none), and still a name a
#: person reads. Beyond it, the name is cut and ends with a hash of the whole, so that two long
#: names stay apart.
MAX_COLUMN_NAME_LENGTH = 63
_NAME_HASH_LENGTH = 8

#: The longest label and description a statistic takes. A label made from the choices is cut there.
MAX_LABEL_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 1000

#: The longest attribute field and value a statistic filters on. A field is an identifier of the
#: dataset's schema; a value is one an object's attribute takes to be told apart — a category, a
#: color —, a few words at most, never a text.
MAX_ATTRIBUTE_FIELD_LENGTH = 128
MAX_ATTRIBUTE_VALUE_LENGTH = 512

#: What a column name is made of: ASCII lower-case letters, digits and underscores, a letter first.
#: Nothing else reaches a table: a dot would be read as a nested field, a leading underscore names
#: the columns Lance adds to a query's result (`_rowid`, `_distance`).
COLUMN_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"

_AREA_UNIT = "px²"
_NOT_IN_A_NAME = re.compile(r"[^a-z0-9]+")

#: The lower-case letters a Unicode decomposition does not bring to ASCII, as a name writes them.
_LETTERS_WITHOUT_DECOMPOSITION = str.maketrans(
    {"ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i"}
)


class AttributeFilter(BaseModel):
    """Counts only the annotations whose object has an attribute at a value, or only such objects.

    Attributes:
        field: The attribute: a field of the dataset's objects.
        value: The value it must have, as text — ``true`` or ``false`` for a yes-or-no field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(min_length=1, max_length=MAX_ATTRIBUTE_FIELD_LENGTH)
    value: str = Field(min_length=1, max_length=MAX_ATTRIBUTE_VALUE_LENGTH)


class StatisticChoices(BaseModel):
    """The choices a statistic is composed of.

    Attributes:
        level: What the statistic gives one value for.
        element: What it measures: an annotation kind by its `DatasetInfo` slot (`bbox`), or
            `entity` for the objects.
        measure: How it measures them.
        aggregation: How several areas become one value. Required for an area, none for a count.
        attribute: Counts only the annotations whose object has this attribute value, or only
            such objects; per object, the other objects get no value.
        origin: Counts only the annotations of this origin.
        review_status: Counts only a model's annotations at this review status. It implies the
            model's origin, which it sets when none is given: the same statistic, the same name.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: StatisticLevel
    element: str
    measure: StatisticMeasure
    aggregation: StatisticAggregation | None = None
    attribute: AttributeFilter | None = None
    origin: AnnotationOrigin | None = None
    review_status: ReviewStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def _review_implies_a_model(cls, data: Any) -> Any:
        """Give a statistic on a review status the model's origin, which it implies."""
        if isinstance(data, dict) and data.get("review_status") is not None and data.get("origin") is None:
            return {**data, "origin": AnnotationOrigin.MODEL}
        return data

    @model_validator(mode="after")
    def _check_meaningful(self) -> StatisticChoices:
        """Refuse a combination that measures nothing meaningful."""
        if self.element not in ELEMENT_NAMES:
            known = ", ".join(sorted(ELEMENT_NAMES))
            raise ValueError(f"Unknown element '{self.element}': a statistic measures one of {known}.")
        if self.level is StatisticLevel.ENTITY and self.element == ENTITY_ELEMENT:
            raise ValueError("A statistic per object measures its annotations, not the objects themselves.")
        if self.measure is not StatisticMeasure.COUNT and self.element not in ELEMENTS_WITH_AREA:
            raise ValueError(f"Only boxes and masks have an area; '{self.element}' can only be counted.")
        if self.measure is StatisticMeasure.COUNT and self.aggregation is not None:
            raise ValueError("A count is one value already: it takes no aggregation.")
        if self.measure is not StatisticMeasure.COUNT and self.aggregation is None:
            raise ValueError("Several areas need an aggregation to make one value: mean, min, max or sum.")
        if self.element == ENTITY_ELEMENT and (self.origin is not None or self.review_status is not None):
            raise ValueError("Objects have no origin nor review status: filter the annotations instead.")
        if self.origin is AnnotationOrigin.NOT_MODEL and self.review_status is not None:
            raise ValueError("Only a model's annotations are reviewed: a review status needs the model origin.")
        if self.review_status is not None and not is_reviewable_element(self.element):
            raise ValueError(f"No interface reviews {ELEMENT_NAMES[self.element]}: they have no review status.")
        return self

    @property
    def version(self) -> int:
        """The version of the measure's computation."""
        return MEASURE_VERSIONS[self.measure]

    @property
    def value_type(self) -> Literal["int", "float"]:
        """The type of the values: whole numbers for a count, decimals otherwise."""
        return "int" if self.measure is StatisticMeasure.COUNT else "float"

    @property
    def unit(self) -> str:
        """The unit of the values: pixels for an area, none for a count or a share of the image."""
        return _AREA_UNIT if self.measure is StatisticMeasure.AREA else ""

    def column_name(self) -> str:
        """The column the statistic's values go to, which says what they are.

        In snake_case, with the unit in the name: ``bbox_count``, ``bbox_area_mean_px``,
        ``mask_to_image_ratio_max``. A filter adds what it keeps — ``bbox_count_category_dog``,
        ``bbox_count_by_model``, ``bbox_count_by_model_pending`` — and a measure past its first
        version adds it, ``_v2``. An attribute's text is transliterated to ASCII, so that a value's
        letters do not vanish from its name: `Vélo` gives `velo`, `Straße` gives `strasse`.

        The name a statistic is stored under is its column for good: the library keeps it
        (`StatisticRegistry.add`), whatever this method would name the same choices later.
        """
        if self.measure is StatisticMeasure.COUNT:
            parts = [self.element, "count"]
        elif self.measure is StatisticMeasure.AREA:
            parts = [self.element, "area", _aggregation_value(self.aggregation), "px"]
        else:
            parts = [self.element, "to_image_ratio", _aggregation_value(self.aggregation)]
        if self.attribute is not None:
            parts += [_name_part(self.attribute.field), _name_part(self.attribute.value)]
        if self.origin is AnnotationOrigin.MODEL:
            parts.append("by_model")
        elif self.origin is AnnotationOrigin.NOT_MODEL:
            parts.append("not_by_model")
        if self.review_status is not None:
            parts.append(self.review_status.value)
        if self.version > 1:
            parts.append(f"v{self.version}")
        return _bounded("_".join(parts))

    def default_label(self) -> str:
        """A label that says in words what the statistic measures, for a person who gave none."""
        element = ELEMENT_NAMES[self.element]
        if self.measure is StatisticMeasure.COUNT:
            label = f"Number of {element}"
        else:
            aggregation = _aggregation_value(self.aggregation)
            what = "area" if self.measure is StatisticMeasure.AREA else "share of the image"
            label = f"{aggregation.capitalize()} {what} of the {element}"
        conditions = []
        if self.attribute is not None:
            conditions.append(f"{self.attribute.field} {self.attribute.value}")
        if self.origin is AnnotationOrigin.MODEL:
            conditions.append("made by a model")
        elif self.origin is AnnotationOrigin.NOT_MODEL:
            conditions.append("not made by a model")
        if self.review_status is not None:
            conditions.append(f"{self.review_status.value} review")
        if self.version > 1:
            conditions.append(f"version {self.version}")
        label = f"{label}, {', '.join(conditions)}" if conditions else label
        return label if len(label) <= MAX_LABEL_LENGTH else f"{label[: MAX_LABEL_LENGTH - 1]}…"


class StatisticDefinition(BaseModel):
    """A statistic of the library, as people composed it.

    Attributes:
        name: The column its values go to, unique per level: named after its choices when it was
            composed (`StatisticChoices.column_name`), then kept as it was stored.
        level: What it gives one value for.
        choices: What it is composed of.
        label: What a person reads in place of the name.
        description: What a person wrote about it, if anything.
        unit: The unit of its values.
        value_type: The type of its values.
        version: The version of its measure's computation.
        created_at: When it was composed.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=COLUMN_NAME_PATTERN, max_length=MAX_COLUMN_NAME_LENGTH)
    level: StatisticLevel
    choices: StatisticChoices
    label: str = Field(min_length=1, max_length=MAX_LABEL_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    unit: str
    value_type: Literal["int", "float"]
    version: int
    created_at: datetime

    @model_validator(mode="after")
    def _agrees_with_its_choices(self) -> StatisticDefinition:
        """Refuse a definition that says otherwise than its choices: its table, or its column's type.

        A definition can also come back from a job's parameters, which anybody can send. One whose
        level is not its choices' would write its values into the other level's table; one whose
        type is not its measure's would make a column the right values can never go to.
        """
        if self.level is not self.choices.level:
            raise ValueError(f"The statistic is per {self.level.value}, its choices per {self.choices.level.value}.")
        if self.value_type != self.choices.value_type or self.unit != self.choices.unit:
            raise ValueError(
                f"The statistic's values are {self.value_type} in '{self.unit}', its measure's "
                f"{self.choices.value_type} in '{self.choices.unit}'."
            )
        return self

    @property
    def is_current(self) -> bool:
        """Whether its measure is computed today as when it was composed.

        A statistic composed before its measure changed is no longer computed: a job would write
        values of the new computation into the column of the old one. The same choices compose the
        statistic of the new version, in a column of its own.
        """
        return self.version == MEASURE_VERSIONS[self.choices.measure]


def is_reviewable_element(element: str) -> bool:
    """Whether a model's annotations of an element have a review status a statistic can filter on.

    Args:
        element: An annotation kind's `DatasetInfo` slot, or `entity` for the objects.

    Returns:
        True for an annotation kind an interface reviews; False for the objects, and for the other
        kinds.
    """
    if element == ENTITY_ELEMENT or element not in ELEMENT_NAMES:
        return False
    return is_reviewable_annotation(canonical_family_spec_for_slot(element).base_schema)


def define_statistic(
    choices: StatisticChoices, label: str | None = None, description: str = ""
) -> StatisticDefinition:
    """The statistic these choices compose, named after them.

    Args:
        choices: What it is composed of.
        label: What a person reads in place of its name; one is made from the choices if none.
        description: What a person writes about it.

    Returns:
        The statistic, with its name, unit, type and version derived from the choices.
    """
    stripped = (label or "").strip()
    return StatisticDefinition(
        name=choices.column_name(),
        level=choices.level,
        choices=choices,
        label=stripped or choices.default_label(),
        description=description.strip(),
        unit=choices.unit,
        value_type=choices.value_type,
        version=choices.version,
        created_at=datetime.now(timezone.utc),
    )


def _aggregation_value(aggregation: StatisticAggregation | None) -> str:
    if aggregation is None:  # pragma: no cover - `StatisticChoices` requires one for an area
        raise ValueError("An area needs an aggregation.")
    return aggregation.value


def _name_part(text: str) -> str:
    """A piece of text as it can stand in a column name: ASCII, lower case, words joined by underscores.

    Accents go (`Vélo` gives `velo`), and the letters a decomposition does not reach are written
    out (`Straße` gives `strasse`, `Øre` gives `ore`).
    """
    lowered = text.lower().translate(_LETTERS_WITHOUT_DECOMPOSITION)
    ascii_text = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    part = _NOT_IN_A_NAME.sub("_", ascii_text).strip("_")
    # A value of symbols alone, or of another script, keeps a name of its own.
    return part or f"value_{_short_hash(text)}"


def _bounded(name: str) -> str:
    """The name, cut to the longest a column name takes, a hash of the whole keeping it apart."""
    if len(name) <= MAX_COLUMN_NAME_LENGTH:
        return name
    head = name[: MAX_COLUMN_NAME_LENGTH - _NAME_HASH_LENGTH - 1].rstrip("_")
    return f"{head}_{_short_hash(name)}"


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_NAME_HASH_LENGTH]
