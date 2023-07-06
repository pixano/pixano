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


def objects_tableToDF(data_table: pa.Table, field: str) -> pd.DataFrame:
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
    except Exception:
        print("ERROR: Unable to convert table Pandas DataFrame")
        return None


def numeric_features_stats(df: pd.DataFrame, field: str) -> list[dict]:
    """Compute numerical statistics (histogram)

    Args:
        df (pd.DataFrame): Input DataFrame
        field (str): Selected field

    Returns:
        dict: Statistics dictionary
    """

    counts, bins = np.histogram(df[field])
    res = []
    for i in range(len(counts)):
        res.append(
            {"bin_start": bins[i], "bin_end": bins[i + 1], "sample_count": counts[i]}
        )
    return res


def categorical_feature_stats(df: pd.DataFrame, field: str, title: str) -> dict:
    """Compute categorical statistics

    Args:
        df (pd.DataFrame): Input DataFrame
        field (str): Selected field
        title (str): Field title

    Returns:
        dict: Statistics dictionary
    """

    counts = df[field].value_counts()
    data = [{"key": k, "value": v} for k, v in counts.items()]
    return {"title": title, "x_title": "count", "y_title": field, "data": data}
