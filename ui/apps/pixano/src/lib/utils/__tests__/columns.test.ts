/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  columnLabel,
  columnLabelOf,
  columnNameLabel,
  describeTableColumns,
  formatColumnLabel,
  GROUP_CELL_TYPE,
  labelWithUnit,
  shownValue,
  STATISTIC_CELL_TYPE,
  undescribedComputedColumns,
  valueLabel,
} from "../columns";
import type { ColumnDescriptorResponse } from "$lib/api/restTypes";

function column(changes: Partial<ColumnDescriptorResponse>): ColumnDescriptorResponse {
  return {
    name: "split",
    type: "str",
    collection: false,
    source: "base",
    filterable: true,
    sortable: true,
    searchable: false,
    indexed: false,
    operators: ["eq"],
    values_complete: true,
    ...changes,
  };
}

const MEAN_AREA = column({
  name: "record_statistics.bbox_area_mean_px",
  type: "float",
  source: "statistics",
  table: "record_statistics",
  label: "Mean area of the boxes",
  unit: "px²",
});

const CLUSTERS = column({
  name: "record_clusters.job-1",
  type: "int",
  source: "clusters",
  table: "record_clusters",
  label: "Clusters — HDBSCAN, groups of 10 or more, 2026-11-06 15:40 UTC",
  values: ["-1", "0", "1"],
  value_labels: { "-1": "Noise" },
});

describe("formatColumnLabel", () => {
  it("title-cases every underscore-separated word", () => {
    expect(formatColumnLabel("created_at")).toBe("Created At");
    expect(formatColumnLabel("created_at_utc")).toBe("Created At Utc");
  });

  it("strips the leading underscore of system columns", () => {
    expect(formatColumnLabel("_distance")).toBe("Distance");
  });

  it("handles single words and empty strings", () => {
    expect(formatColumnLabel("id")).toBe("Id");
    expect(formatColumnLabel("split")).toBe("Split");
    expect(formatColumnLabel("")).toBe("");
  });
});

describe("what a column is called", () => {
  it("is a statistic's label, with its unit", () => {
    expect(columnLabel(MEAN_AREA)).toBe("Mean area of the boxes (px²)");
    expect(columnLabel({ ...MEAN_AREA, unit: null })).toBe("Mean area of the boxes");
  });

  it("is any other column's name, made readable", () => {
    expect(columnLabel(column({ name: "created_at" }))).toBe("Created At");
    expect(columnLabelOf([MEAN_AREA], "split")).toBe("Split");
    expect(columnLabelOf([MEAN_AREA], MEAN_AREA.name)).toBe("Mean area of the boxes (px²)");
  });
});

describe("the table's columns, named as the explorer names them", () => {
  it("shows a statistic by its label, as a statistic, and leaves the other columns be", () => {
    const table = {
      columns: [
        { name: "id", type: "str" },
        { name: MEAN_AREA.name, type: STATISTIC_CELL_TYPE },
      ],
      rows: [],
    };

    expect(describeTableColumns(table, [column({ name: "id" }), MEAN_AREA]).columns).toEqual([
      { name: "id", type: "str" },
      { name: MEAN_AREA.name, type: STATISTIC_CELL_TYPE, label: "Mean area of the boxes (px²)" },
    ]);
  });

  it("shows a run of a clustering by its label, as its groups, its noise by name", () => {
    const table = { columns: [{ name: CLUSTERS.name, type: STATISTIC_CELL_TYPE }], rows: [] };

    expect(describeTableColumns(table, [CLUSTERS]).columns).toEqual([
      {
        name: CLUSTERS.name,
        type: GROUP_CELL_TYPE,
        label: CLUSTERS.label,
        valueLabels: { "-1": "Noise" },
      },
    ]);
  });
});

describe("what a value is called", () => {
  it("is the label its column gives it, else the value", () => {
    expect(valueLabel(CLUSTERS, "-1")).toBe("Noise");
    expect(valueLabel(CLUSTERS, "0")).toBe("0");
    expect(valueLabel(MEAN_AREA, "-1")).toBe("-1");
    expect(valueLabel(undefined, "train")).toBe("train");
  });

  it("is never what an object holds by inheritance", () => {
    expect(valueLabel(CLUSTERS, "constructor")).toBe("constructor");
  });
});

describe("what a cell shows", () => {
  const groups = { valueLabels: { "-1": "Noise" } };

  it("is the label its column gives a value, else the value for the cell to format", () => {
    expect(shownValue(groups, -1)).toBe("Noise");
    expect(shownValue(groups, 3)).toBe(3);
    expect(shownValue({}, -1)).toBe(-1);
  });

  it("leaves what is no single value, and what an object holds by inheritance", () => {
    const histogram = { name: "x", type: "int", histogram: [] };
    expect(shownValue(groups, histogram)).toBe(histogram);
    expect(shownValue(groups, "toString")).toBe("toString");
  });
});

describe("a computed column the explorer's columns do not describe yet", () => {
  const table = {
    columns: [
      { name: "id", type: "str" },
      { name: MEAN_AREA.name, type: STATISTIC_CELL_TYPE },
      { name: "record_statistics.bbox_count", type: STATISTIC_CELL_TYPE },
      { name: CLUSTERS.name, type: STATISTIC_CELL_TYPE },
    ],
    rows: [],
  };

  it("is named after its column, its table's prefix left out", () => {
    expect(columnNameLabel("record_statistics.bbox_count")).toBe("Bbox Count");
    expect(columnLabelOf([], "record_statistics.bbox_count")).toBe("Bbox Count");
  });

  it("is named clusters for a run of a clustering, whose name is an identifier", () => {
    expect(columnNameLabel(CLUSTERS.name)).toBe("Clusters");
  });

  it("is found, a statistic or a run of a clustering, for the columns to be read again", () => {
    expect(undescribedComputedColumns(table, [column({ name: "id" }), MEAN_AREA])).toEqual([
      "record_statistics.bbox_count",
      CLUSTERS.name,
    ]);
    expect(
      undescribedComputedColumns(table, [
        MEAN_AREA,
        column({ name: "record_statistics.bbox_count" }),
        CLUSTERS,
      ]),
    ).toEqual([]);
  });

  it("joins its unit to a label", () => {
    expect(labelWithUnit("Mean area", "px²")).toBe("Mean area (px²)");
    expect(labelWithUnit("Boxes", "")).toBe("Boxes");
  });
});
