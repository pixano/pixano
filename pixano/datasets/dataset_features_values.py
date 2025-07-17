# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, NewType, Union

from pydantic import BaseModel


TableName = NewType("TableName", str)


@dataclass
class Constraint:
    """Constraint values.

    Attributes:
        name: name of the field.
        restricted: whether allowed values are restricted to given values, or user may enter new values.
        values: list of allowed values.
    """

    name: str
    restricted: bool
    values: List[Union[int, float, str, bool]]


ConstraintDict = Dict[TableName, List[Constraint]]
"""Dict of Constraint, by table.

Keys are table names (`TableName`), and values are list of constraints (`Constraint`).
"""


class DatasetFeaturesValues(BaseModel):
    """Constraints for the dataset features values.

    Attributes:
        items: Constraints for the dataset item table.
        views: Constraints for the dataset view tables.
        entities: Constraints for the dataset entity tables.
        annotations: Constraints for the dataset annotation tables.
    """

    items: ConstraintDict = {}
    views: ConstraintDict = {}
    entities: ConstraintDict = {}
    annotations: ConstraintDict = {}

    def to_json(self, json_fp: Path) -> None:
        """Save DatasetFeaturesValues to json file."""
        json_fp.write_text(json.dumps(self.model_dump(), indent=4), encoding="utf-8")

    @staticmethod
    def from_json(json_fp: Path) -> "DatasetFeaturesValues":
        """Load DatasetFeaturesValues from json file."""
        fv_json = json.loads(json_fp.read_text(encoding="utf-8"))
        fv = DatasetFeaturesValues.model_validate(fv_json)

        return fv

    def add_constraint(
        self,
        kind: Literal["items", "views", "entities", "annotations"],
        table: TableName,
        field_name: str,
        values: List[Union[int, float, str, bool]],
        restricted: bool = True,
    ):
        """Add or replace a constraint.

        Args:
            kind: Kind of field, amongst "items", "views", "entities", "annotations".
            table: Table name (as in DatasetItem schema)
            field_name: Name of the field to constrain.
            values: List of allowed values.
            restricted: True if no other values are allowed.
        """
        constraint_dict: ConstraintDict = getattr(self, kind)

        # Ensure the list exists for the given table
        if table not in constraint_dict:
            constraint_dict[table] = []

        # Check if the field already has a constraint → update it if so
        for constraint in constraint_dict[table]:
            if constraint.name == field_name:
                constraint.restricted = restricted
                constraint.values = values
                return

        # Otherwise, add a new constraint
        constraint_dict[table].append(Constraint(name=field_name, restricted=restricted, values=values))
