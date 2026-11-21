/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ColumnDescriptorResponse } from "$lib/api/restTypes";
import { STATISTICS_COLUMN_PREFIX } from "$lib/api/statisticsApi";
import type { TableData } from "$lib/types/dataset";

/** The cell type of a statistic's column: its value formatted, or a dash where it has none. */
export const STATISTIC_CELL_TYPE = "statistic";

/**
 * Human-readable label for a record column name.
 *
 * Replaces every underscore, trims the leading one from system columns like
 * `_distance`, and Title-Cases each word: `created_at` → "Created At",
 * `_distance` → "Distance".
 */
export function formatColumnLabel(name: string): string {
  return name
    .replace(/^_+/, "")
    .replaceAll("_", " ")
    .trim()
    .split(/\s+/)
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}

/** A label with its unit, when it has one: "Mean area of the boxes (px²)". */
export function labelWithUnit(label: string, unit: string | null | undefined): string {
  return unit ? `${label} (${unit})` : label;
}

/**
 * What a column is called from its name alone, when nothing describes it: a statistic named after
 * its column, its table's prefix left out — the columns may not be read yet.
 */
export function columnNameLabel(name: string): string {
  return formatColumnLabel(
    name.startsWith(STATISTICS_COLUMN_PREFIX) ? name.slice(STATISTICS_COLUMN_PREFIX.length) : name,
  );
}

/** What a column is called: a statistic by its label and unit, any other column by its name. */
export function columnLabel(
  column: Pick<ColumnDescriptorResponse, "name" | "label" | "unit">,
): string {
  return column.label ? labelWithUnit(column.label, column.unit) : columnNameLabel(column.name);
}

/** What the column of this name is called, among the explorer's columns. */
export function columnLabelOf(columns: ColumnDescriptorResponse[], name: string): string {
  const column = columns.find((candidate) => candidate.name === name);
  return column ? columnLabel(column) : columnNameLabel(name);
}

/**
 * The statistics a page of records carries that the explorer's columns do not describe: computed
 * since the columns were read. The columns are to be read again.
 */
export function undescribedStatisticColumns(
  table: TableData,
  columns: ColumnDescriptorResponse[],
): string[] {
  const described = new Set(columns.map((column) => column.name));
  return table.columns
    .map((column) => column.name)
    .filter((name) => name.startsWith(STATISTICS_COLUMN_PREFIX) && !described.has(name));
}

/**
 * The table's columns named as the explorer's columns name them: a statistic's column, which
 * a page of records carries under its table's prefix, by its label and unit, and shown as a
 * statistic. The other columns keep what the page says of them.
 */
export function describeTableColumns(
  table: TableData,
  columns: ColumnDescriptorResponse[],
): TableData {
  const labelled = new Map(
    columns.filter((column) => column.label).map((column) => [column.name, column]),
  );
  return {
    ...table,
    columns: table.columns.map((column) => {
      const described = labelled.get(column.name);
      return described
        ? { ...column, type: STATISTIC_CELL_TYPE, label: columnLabel(described) }
        : column;
    }),
  };
}
