/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ColumnDescriptorResponse } from "$lib/api/restTypes";
import { STATISTICS_COLUMN_PREFIX } from "$lib/api/statisticsApi";
import type { TableColumn, TableData } from "$lib/types/dataset";
import { isScalarValue } from "$lib/utils/coreUtils";

/** The cell type of a statistic's column: its value formatted, or a dash where it has none. */
export const STATISTIC_CELL_TYPE = "statistic";

/** The cell type of a run of a clustering's column: a group shown as it is, or a dash. */
export const GROUP_CELL_TYPE = "group";

/** The table of the records' clusters, which a run of a clustering's column is read from. */
export const CLUSTERS_TABLE = "record_clusters";

/**
 * What names a run of a clustering among a record's columns: its table, then the run — as the
 * explorer's filters and sorts name it.
 */
export const CLUSTERS_COLUMN_PREFIX = `${CLUSTERS_TABLE}.`;

/** The prefixes naming the columns a dataset computed from its records, in tables of their own. */
const COMPUTED_COLUMN_PREFIXES = [STATISTICS_COLUMN_PREFIX, CLUSTERS_COLUMN_PREFIX];

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

/** What a run of a clustering's column is called while nothing describes it yet. */
export const UNDESCRIBED_CLUSTERS_LABEL = "Clusters";

/**
 * What a column is called from its name alone, when nothing describes it: a statistic named after
 * its column, its table's prefix left out; a run of a clustering, whose name is an identifier, as
 * clusters — the columns may not be read yet.
 */
export function columnNameLabel(name: string): string {
  if (name.startsWith(CLUSTERS_COLUMN_PREFIX)) return UNDESCRIBED_CLUSTERS_LABEL;
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

/** What a person reads for a value of a column: the label the column gives it, else the value. */
export function valueLabel(
  column: Pick<ColumnDescriptorResponse, "value_labels"> | undefined,
  value: string,
): string {
  const labels = column?.value_labels;
  return labels && Object.hasOwn(labels, value) ? labels[value] : value;
}

/**
 * What a table's cell shows of a value: the label its column gives the value — a clustering's
 * noise —, else the value itself, for the cell to format.
 */
export function shownValue<T>(column: Pick<TableColumn, "valueLabels">, value: T): T | string {
  const labels = column.valueLabels;
  if (!labels || !isScalarValue(value)) return value;
  const key = String(value);
  return Object.hasOwn(labels, key) ? labels[key] : value;
}

/**
 * The computed columns — statistics, runs of a clustering — a page of records carries that the
 * explorer's columns do not describe: computed since the columns were read. The columns are to be
 * read again.
 */
export function undescribedComputedColumns(
  table: TableData,
  columns: ColumnDescriptorResponse[],
): string[] {
  const described = new Set(columns.map((column) => column.name));
  return table.columns
    .map((column) => column.name)
    .filter(
      (name) =>
        COMPUTED_COLUMN_PREFIXES.some((prefix) => name.startsWith(prefix)) && !described.has(name),
    );
}

/**
 * The table's columns named as the explorer's columns name them: a computed column, which a page
 * of records carries under its table's prefix, by its label and unit — a statistic shown as one, a
 * run of a clustering as its groups —, its values by the labels the column gives some of them. The
 * other columns keep what the page says of them.
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
      if (!described) return column;
      const valueLabels = described.value_labels ?? undefined;
      return {
        ...column,
        type: described.table === CLUSTERS_TABLE ? GROUP_CELL_TYPE : STATISTIC_CELL_TYPE,
        label: columnLabel(described),
        ...(valueLabels ? { valueLabels } : {}),
      };
    }),
  };
}
