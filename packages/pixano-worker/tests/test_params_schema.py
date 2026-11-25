# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A kind's parameters as the forms read them: each by itself, its choices where it stands."""

from enum import Enum
from typing import Any

from pixano_worker.kinds import ClusteringKind
from pixano_worker.kinds.base import JobKind, JobParams, Outcome
from pydantic import BaseModel, Field


class Shape(str, Enum):
    """A shape to choose."""

    ROUND = "round"
    SQUARE = "square"


class Corner(BaseModel):
    """A part of a parameter that is no choice: it stays a reference."""

    x: int = 0


class ToyParams(JobParams):
    """Every place an enumeration can stand in a parameter."""

    shape: Shape = Field(default=Shape.ROUND, description="The shape.")
    maybe: Shape | None = None
    shapes: list[Shape] = Field(default_factory=list)
    corners: list[Corner] = Field(default_factory=list)


class ToyKind(JobKind[ToyParams]):
    """A kind whose parameters hold enumerations everywhere."""

    name = "toy-shapes"
    params_model = ToyParams

    def plan(self, reader: Any, params: ToyParams) -> Any:
        return iter(())

    def process(self, reader: Any, payload: dict[str, Any], params: ToyParams) -> Any:
        return None

    def write(self, writer: Any, result: Any, payload: dict[str, Any], params: ToyParams) -> None:
        return None

    def outcome(self, result: Any, payload: dict[str, Any], task_count: int) -> Outcome:
        return Outcome(produced=task_count)


CHOICES = {"type": "string", "enum": ["round", "square"]}


class TestEnumerations:
    def test_a_parameter_carries_its_choices_its_default_and_a_title(self) -> None:
        shape = ToyKind().params_schema()["properties"]["shape"]

        assert shape == {**CHOICES, "default": "round", "description": "The shape.", "title": "Shape"}

    def test_an_optional_one_carries_them_in_its_branch(self) -> None:
        maybe = ToyKind().params_schema()["properties"]["maybe"]

        assert maybe["anyOf"] == [CHOICES, {"type": "null"}]

    def test_a_list_of_them_carries_them_in_its_items(self) -> None:
        assert ToyKind().params_schema()["properties"]["shapes"]["items"] == CHOICES

    def test_a_reference_to_anything_else_stays(self) -> None:
        assert ToyKind().params_schema()["properties"]["corners"]["items"] == {"$ref": "#/$defs/Corner"}

    def test_the_clusterings_algorithm(self) -> None:
        algorithm = ClusteringKind().params_schema()["properties"]["algorithm"]

        assert {key: algorithm[key] for key in ("type", "enum", "default", "title")} == {
            "type": "string",
            "enum": ["kmeans", "hdbscan"],
            "default": "kmeans",
            "title": "Algorithm",
        }
