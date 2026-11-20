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
  labelWithUnit,
  STATISTIC_CELL_TYPE,
  undescribedStatisticColumns,
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
});

describe("a statistic's column the explorer's columns do not describe yet", () => {
  const table = {
    columns: [
      { name: "id", type: "str" },
      { name: MEAN_AREA.name, type: STATISTIC_CELL_TYPE },
      { name: "record_statistics.bbox_count", type: STATISTIC_CELL_TYPE },
    ],
    rows: [],
  };

  it("is named after its column, its table's prefix left out", () => {
    expect(columnNameLabel("record_statistics.bbox_count")).toBe("Bbox Count");
    expect(columnLabelOf([], "record_statistics.bbox_count")).toBe("Bbox Count");
  });

  it("is found, for the columns to be read again", () => {
    expect(undescribedStatisticColumns(table, [column({ name: "id" }), MEAN_AREA])).toEqual([
      "record_statistics.bbox_count",
    ]);
    expect(
      undescribedStatisticColumns(table, [
        MEAN_AREA,
        column({ name: "record_statistics.bbox_count" }),
      ]),
    ).toEqual([]);
  });

  it("joins its unit to a label", () => {
    expect(labelWithUnit("Mean area", "px²")).toBe("Mean area (px²)");
    expect(labelWithUnit("Boxes", "")).toBe("Boxes");
  });
});
