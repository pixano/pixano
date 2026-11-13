/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { buildQueryString, requestJson } from "./apiClient";
import type { StatisticDefinition } from "./statisticsApi";

/** A histogram of numbers, or the values counted. */
export type OverviewCardKind = "histogram" | "values";

/** What holds a card's values. */
export type OverviewSubject = "record" | "image" | "object";

/** The part of the overview a card belongs to. */
export type OverviewGroup = "records" | "media" | "annotations";

/**
 * A bar of a histogram: the values from `start` to `end`. Of whole values, `end` is the value after
 * the last it counts; of other numbers, the value it stops before — but the last bar ends at the
 * largest value, and counts it.
 */
export interface OverviewBar {
  start: number;
  end: number;
  count: number;
  /** How many of them the filters of the card's own column keep, when it is filtered. */
  selected?: number | null;
  /** The count per split of their record, when the overview counts per split. */
  by_split: Record<string, number>;
}

/** A value of a card of values, and how many hold it. */
export interface OverviewValue {
  value: string;
  count: number;
  /** How many of them the filters of the card's own column keep, when it is filtered. */
  selected?: number | null;
  by_split: Record<string, number>;
}

/** What the overview shows of one thing measured, as `GET /datasets/{id}/overview` answers. */
export interface OverviewCard {
  id: string;
  group: OverviewGroup;
  label: string;
  unit: string;
  subject: OverviewSubject;
  kind: OverviewCardKind;
  /** The records, images or objects the filters keep — but those of its own column, when filtered. */
  population: number;
  /** Those without a value. */
  missing: number;
  /** Those with a value per split, when counted per split: what a split's share is counted out of. */
  counted_by_split: Record<string, number>;
  /** The explorer's column a bar or a value filters the records on; none when the values are not theirs. */
  filter_column: string | null;
  /**
   * Whether the explorer filters the records on its column: the card then counts those the other
   * filters keep, and its bars and values say how many of them its own filters keep.
   */
  filtered?: boolean;
  /** When the statistic it shows was computed, for a statistic's card: annotations edited since are not in it. */
  computed_at?: string | null;
  whole_values: boolean;
  minimum: number | null;
  maximum: number | null;
  mean: number | null;
  median: number | null;
  bars: OverviewBar[];
  /** The values counted, the most held first. */
  values: OverviewValue[];
  distinct: number;
  /** How many hold a value not listed. */
  others: number;
  /** How many of them the filters of its own column keep, when it is filtered. */
  others_selected?: number | null;
  others_by_split: Record<string, number>;
}

/** How a dataset's records, media and annotations spread, over the records the filters keep. */
export interface DatasetOverview {
  records: number;
  total_records: number;
  /**
   * The splits of the records any card counts, in alphabetical order, none named the last: a split
   * keeps its place, and its color, from card to card.
   */
  splits: string[];
  cards: OverviewCard[];
  /** The default statistics the dataset has no values of: their cards come once computed. */
  statistics_to_compute: StatisticDefinition[];
}

/** The explorer's request an overview reads: its filters, its free text, and whether to count per split. */
export interface OverviewRequest {
  filters?: string[];
  q?: string;
  where?: string;
  bySplit?: boolean;
}

/** The overview of the records the explorer's filters keep. */
export function getOverview(datasetId: string, request: OverviewRequest): Promise<DatasetOverview> {
  const query = buildQueryString({
    filter: request.filters,
    q: request.q,
    where: request.where,
    by_split: request.bySplit ? true : undefined,
  });
  return requestJson<DatasetOverview>(`/datasets/${datasetId}/overview${query}`, {}, "getOverview");
}
