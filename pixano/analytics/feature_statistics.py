# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from fractions import Fraction
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa


def compute_additional_data(data_table: pa.Table) -> pd.DataFrame:
    """Convert Table to DataFrame and add resolution and aspect ratio

    Args:
        data_table (pa.Table): Input Table

    Returns:
        pd.DataFrame: DataFrame with added resolution and aspect ratio
    """

    # Take a subset of table without image columns (which can't be converted to pandas)
    if not all(p in data_table.column_names for p in ["width", "height"]):
        return None
    data = data_table.select(["width", "height"]).to_pandas()

    # Compute additional data
    data["resolution"] = data.apply(
        lambda x: str(x["width"]) + "x" + str(x["height"]), axis=1
    )
    data["aspect_ratio"] = data.apply(
        lambda x: str(Fraction(x["width"], x["height"])).replace("/", ":"), axis=1
    )

    return data


def objects_table_to_df(data_table: pa.Table, field: str) -> pd.DataFrame:
    """Convert a field from the objects column to a DataFrame

    Args:
        data_table (pa.Table): Table with an objects column
        field (str): Selected field from the objects column

    Returns:
        pd.DataFrame: Selected field as DataFrame
    """

    try:
        df_objs = data_table.select(["objects"]).to_pandas()
        sel = [{field: d[field]} for objs in df_objs["objects"] for d in objs]
        return pd.DataFrame.from_dict(sel)
    except ValueError as e:
        raise ValueError("Unable to convert table Pandas DataFrame") from e


def categorical_stats(df: pd.DataFrame, split: str, field_name: str) -> list[dict]:
    """Compute feature categorical statistics

    Args:
        df (pd.DataFrame): Input DataFrame
        split (str): DataFrame split
        field_name (str): Selected field

    Returns:
        list[dict]: Feature statistics
    """

    counts = df.value_counts(subset=field_name)
    return [{field_name: k, "counts": v, "split": split} for k, v in counts.items()]


def numerical_stats(
    df: pd.DataFrame, split: str, field_name: str, field_range: list[float] = None
) -> list[dict]:
    """Compute feature numerical statistics

    Args:
        df (pd.DataFrame): Input DataFrame
        split (str): DataFrame split
        field_name (str): Selected field
        field_range (list[float], optional): Selected field range. Defaults to None.

    Returns:
        list[dict]: Feature statistics
    """

    counts, bins = np.histogram(df[field_name], range=field_range)
    return [
        {
            "bin_start": float(bins[i]),
            "bin_end": float(bins[i + 1]),
            "counts": int(counts[i]),
            "split": split,
        }
        for i in range(len(counts))
    ]


def compute_stats(df: pd.DataFrame, split: str, feature: dict[str, Any]) -> list[dict]:
    """Compute feature statistics

    Args:
        df (pd.DataFrame): Input DataFrame
        split (str): DataFrame split
        feature (dict): Selected feature

    Returns:
        list[dict]: Feature statistics
    """

    # Categorical
    if feature["type"] == "categorical":
        return categorical_stats(df, split, feature["name"])
    # Numerical
    elif feature["type"] == "numerical":
        return numerical_stats(df, split, feature["name"], feature.get("range", None))
    # Else
    else:
        return []
