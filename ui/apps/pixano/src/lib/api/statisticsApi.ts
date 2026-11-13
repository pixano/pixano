/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** What a statistic gives one value for. */
export type StatisticLevel = "record" | "entity";
/** How a statistic measures what it measures. */
export type StatisticMeasure = "count" | "area" | "image_ratio";
/** How several areas become one value. */
export type StatisticAggregation = "mean" | "min" | "max" | "sum";
/** Whose annotations a statistic counts. */
export type AnnotationOrigin = "model" | "not_model";

/** Counts only the annotations whose object has an attribute at a value, or only such objects. */
export type AttributeFilter = { field: string; value: string };

/** The choices a statistic is composed of, as the backend validates them. */
export type StatisticChoices = {
  level: StatisticLevel;
  element: string;
  measure: StatisticMeasure;
  aggregation?: StatisticAggregation | null;
  attribute?: AttributeFilter | null;
  origin?: AnnotationOrigin | null;
  review_status?: string | null;
};

/** A statistic of the library, as people composed it. */
export type StatisticDefinition = {
  /** Its column, unique per level. */
  name: string;
  level: StatisticLevel;
  choices: StatisticChoices;
  label: string;
  description: string;
  unit: string;
  value_type: "int" | "float";
  version: number;
  created_at: string;
};

/**
 * What names a statistic among a record's columns: its table, then its column — as the explorer's
 * filters and sorts name it, apart from a record's own column of the same name.
 */
export const STATISTICS_COLUMN_PREFIX = "record_statistics.";
