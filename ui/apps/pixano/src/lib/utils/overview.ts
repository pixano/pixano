/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  OverviewBar,
  OverviewCard,
  OverviewGroup,
  OverviewSubject,
} from "$lib/api/overviewApi";
import type { StatisticDefinition } from "$lib/api/statisticsApi";
import { formatStatisticValue } from "$lib/statistics/format";
import { parseFilter, serializeFilter } from "$lib/utils/recordFilters";

/**
 * The least gap between two splits' shares of a bar, or of a value, that the overview points out:
 * a tenth of each split — ten points of percentage.
 */
export const NOTABLE_SPLIT_GAP = 0.1;

/** How far below `NOTABLE_SPLIT_GAP` a gap still reaches it: what the arithmetic of shares loses. */
const SHARE_TOLERANCE = 1e-9;

/** A share written as a percentage, with this many decimals. */
export const PERCENT = 100;
const SHARE_DECIMALS = 1;

/**
 * The explorer's limits on a request's filters — `MAX_FILTERS` and `MAX_VALUE_LENGTH` in
 * `pixano.api.query` —, which a filter added from a card must keep: past them, the server refuses
 * the request.
 */
export const MAX_FILTERS = 8;
export const MAX_FILTER_VALUE_LENGTH = 512;

/** The card of the records' split: its own values are what a comparison of splits splits on. */
export const SPLIT_CARD_ID = "field:split";

/** What a person reads for the split of a record that names none. */
export const NO_SPLIT_LABEL = "No split";

/** What a person reads for the values a card of values does not list: no value is written so. */
export const OTHERS_LABEL = "(others)";

/** What a card's values are held by, one and many. */
export const SUBJECT_WORDS: Record<OverviewSubject, { one: string; many: string }> = {
  record: { one: "record", many: "records" },
  image: { one: "image", many: "images" },
  object: { one: "object", many: "objects" },
};

/** The parts of the overview, in their order, with their titles. */
export const GROUP_TITLES: Record<OverviewGroup, string> = {
  records: "Records",
  media: "Media",
  annotations: "Annotations",
};
const GROUP_ORDER: OverviewGroup[] = ["records", "media", "annotations"];

/** A series of bars of a card's chart: one for every value, or one per split. */
export interface ChartSeries {
  label: string;
  values: number[];
  /** The split's place among the overview's splits, so that it keeps its color from card to card. */
  colorIndex: number;
}

/** What a card's chart draws. */
export interface CardChart {
  /** A label per bar. */
  labels: string[];
  /** The count of each bar, whatever the series show: what a table of the values lists. */
  counts: number[];
  /** One series, the counts; or one per split, the share of the split each bar holds. */
  series: ChartSeries[];
  /** Whether the series are shares of their split rather than counts. */
  shares: boolean;
  /** Per bar, whether the splits' shares of it differ enough to point it out. */
  notable: boolean[];
  /** Per bar, whether clicking it filters the records. */
  clickable: boolean[];
  /** Per bar, whether the filters of the card's own column keep some of its records. */
  selected: boolean[];
}

/** A number as a person reads it, as a statistic's column shows it; whole numbers whole. */
export function formatValue(value: number, whole: boolean): string {
  return whole ? Math.round(value).toLocaleString() : formatStatisticValue(value);
}

/** What a bar holds, as its axis names it: one value, a range of whole values, or of any values. */
export function barLabel(bar: OverviewBar, whole: boolean): string {
  const last = whole ? bar.end - 1 : bar.end;
  if (last <= bar.start) return formatValue(bar.start, whole);
  return `${formatValue(bar.start, whole)}–${formatValue(last, whole)}`;
}

/** What a person reads for a split. */
export function splitLabel(split: string): string {
  return split === "" ? NO_SPLIT_LABEL : split;
}

/** The column a filter token names; none for a token of no filter's shape. */
function columnOf(token: string): string | null {
  return parseFilter(token)?.col ?? null;
}

/** The token of one filter of a column. */
function filterToken(column: string, op: string, value: number | string): string {
  return serializeFilter({ col: column, op, values: [String(value)] });
}

/**
 * The explorer's filters that keep the records of a bar: those whose value is its whole value, or in
 * its range — the last bar keeps its end. None for a card whose values are not the records' own.
 */
export function filtersForBar(card: OverviewCard, index: number): string[] | null {
  const bar = card.bars[index];
  const column = card.filter_column;
  if (column === null || bar === undefined) return null;
  if (card.whole_values) {
    const last = bar.end - 1;
    if (last <= bar.start) return [filterToken(column, "eq", bar.start)];
    return [filterToken(column, "gte", bar.start), filterToken(column, "lte", last)];
  }
  const isLast = index === card.bars.length - 1;
  return [
    filterToken(column, "gte", bar.start),
    filterToken(column, isLast ? "lte" : "lt", bar.end),
  ];
}

/**
 * The explorer's filter that keeps the records holding a value: none for the values a card does not
 * list, for one longer than a filter takes, nor for a card whose values are not the records' own.
 */
export function filtersForValue(card: OverviewCard, index: number): string[] | null {
  const value = card.values[index];
  if (card.filter_column === null || value === undefined) return null;
  if (value.value.length > MAX_FILTER_VALUE_LENGTH) return null;
  return [filterToken(card.filter_column, "eq", value.value)];
}

/** The filters that keep the records of a card's bar, or of its value; none where they cannot. */
export function filtersForIndex(card: OverviewCard, index: number): string[] | null {
  return card.kind === "histogram" ? filtersForBar(card, index) : filtersForValue(card, index);
}

/** The explorer's filters with those on a column replaced: a bar clicked keeps that bar alone. */
export function withColumnFilters(filters: string[], column: string, added: string[]): string[] {
  return [...filters.filter((token) => columnOf(token) !== column), ...added];
}

/** Whether the filters on a column are, all of them and only them, those given. */
function filtersAre(filters: string[], column: string, tokens: string[]): boolean {
  const current = filters.filter((token) => columnOf(token) === column);
  return current.length === tokens.length && tokens.every((token) => current.includes(token));
}

/**
 * The explorer's filters once a card's bar is clicked: those keeping its records, in place of the
 * card's own; clicked again, the card's own are dropped and every record comes back. None when the
 * bar filters nothing.
 */
export function filtersAfterClick(
  filters: string[],
  card: OverviewCard,
  index: number,
): string[] | null {
  const column = card.filter_column;
  const tokens = filtersForIndex(card, index);
  if (column === null || tokens === null) return null;
  return withColumnFilters(filters, column, filtersAre(filters, column, tokens) ? [] : tokens);
}

/** Whether the card's own filters keep the records of this bar alone: clicking it again clears them. */
export function barKept(filters: string[], card: OverviewCard, index: number): boolean {
  const tokens = filtersForIndex(card, index);
  return (
    card.filter_column !== null &&
    tokens !== null &&
    filtersAre(filters, card.filter_column, tokens)
  );
}

/** How many bars a card's chart draws: its bars, or its values and the others counted together. */
export function itemCount(card: OverviewCard): number {
  return card.kind === "histogram"
    ? card.bars.length
    : card.values.length + (card.others > 0 ? 1 : 0);
}

/** For each card, per bar, whether the explorer's filters keep its records alone (`barKept`). */
export function keptBars(cards: OverviewCard[], filters: string[]): Record<string, boolean[]> {
  return Object.fromEntries(
    cards.map((card) => [
      card.id,
      Array.from({ length: itemCount(card) }, (_unused, index) => barKept(filters, card, index)),
    ]),
  );
}

/** The explorer's filters without those of a card's column: what its Clear does. */
export function filtersWithoutCard(filters: string[], card: OverviewCard): string[] {
  return card.filter_column === null ? filters : withColumnFilters(filters, card.filter_column, []);
}

/** Whether the server takes this many filters. */
export function withinFilterLimit(filters: string[]): boolean {
  return filters.length <= MAX_FILTERS;
}

/** A share of a total, none when the total is. */
function shareOf(count: number, total: number): number {
  return total > 0 ? count / total : 0;
}

/** A share, from 0 to 1, as a person reads it: "12.5%". */
export function formatShare(share: number): string {
  return `${(share * PERCENT).toFixed(SHARE_DECIMALS)}%`;
}

/** What the outline of a bar pointed out means. */
export function notableExplanation(): string {
  const points = Math.round(NOTABLE_SPLIT_GAP * PERCENT);
  return `Outlined bars: the splits' shares differ by ${points} points or more, or a split lacks a value`;
}

/**
 * What a card's chart draws: its bars, or its values and the others counted together, with the bars
 * whose records the filters of its own column keep, and those clicking filters on.
 *
 * Per split, each split is a series of the share of its own values each bar holds — splits of any
 * size compare —, colored by its place among the overview's splits, and a bar is pointed out when
 * two splits' shares of it differ by `NOTABLE_SPLIT_GAP` or more, or, for a value, when a split holds
 * it and another none. The split card itself is never compared: each split is all of its own bar.
 */
export function cardChart(card: OverviewCard, splits: string[]): CardChart {
  const items =
    card.kind === "histogram"
      ? card.bars.map((bar) => ({
          label: barLabel(bar, card.whole_values),
          count: bar.count,
          selected: bar.selected ?? 0,
          by_split: bar.by_split,
        }))
      : [
          ...card.values.map((value) => ({
            label: value.value,
            count: value.count,
            selected: value.selected ?? 0,
            by_split: value.by_split,
          })),
          ...(card.others > 0
            ? [
                {
                  label: OTHERS_LABEL,
                  count: card.others,
                  selected: card.others_selected ?? 0,
                  by_split: card.others_by_split,
                },
              ]
            : []),
        ];
  const labels = items.map((item) => item.label);
  const counts = items.map((item) => item.count);
  const clickable = items.map((_item, index) => filtersForIndex(card, index) !== null);
  const selected = items.map((item) => card.filtered === true && item.selected > 0);
  const compared =
    card.id === SPLIT_CARD_ID
      ? []
      : splits.filter((split) => (card.counted_by_split[split] ?? 0) > 0);
  if (compared.length < 2) {
    return {
      labels,
      counts,
      series: [{ label: "", values: counts, colorIndex: 0 }],
      shares: false,
      notable: items.map(() => false),
      clickable,
      selected,
    };
  }
  const series = compared.map((split) => ({
    label: splitLabel(split),
    values: items.map((item) =>
      shareOf(item.by_split[split] ?? 0, card.counted_by_split[split] ?? 0),
    ),
    colorIndex: splits.indexOf(split),
  }));
  const notable = items.map((_item, index) => {
    const shares = series.map((one) => one.values[index]);
    const gap = Math.max(...shares) - Math.min(...shares);
    const heldBySome =
      card.kind === "values" &&
      shares.some((share) => share > 0) &&
      shares.some((share) => share === 0);
    return gap >= NOTABLE_SPLIT_GAP - SHARE_TOLERANCE || heldBySome;
  });
  return { labels, counts, series, shares: true, notable, clickable, selected };
}

/**
 * Whether a card's values are as many as what holds them, more than it lists — an identifier, a free
 * text —: its chart would only count ones. A few values, each held once, are still drawn.
 */
export function allDistinct(card: OverviewCard): boolean {
  const counted = card.population - card.missing;
  return card.kind === "values" && card.others > 0 && card.distinct === counted;
}

/** A count and the word for what it counts, one or many: "1 record", "3 objects". */
export function counted(count: number, words: { one: string; many: string }): string {
  return `${count.toLocaleString()} ${count === 1 ? words.one : words.many}`;
}

/** What a card says of its values, beside its chart: how many hold one, their summary, those missing. */
export function cardSummary(card: OverviewCard): string[] {
  const words = SUBJECT_WORDS[card.subject];
  const held = card.population - card.missing;
  if (card.population === 0) return [`No ${words.many}`];
  if (held === 0) {
    return [
      card.population === 1
        ? `The ${words.one} holds no value`
        : `None of the ${counted(card.population, words)} holds a value`,
    ];
  }
  const parts = [counted(held, words)];
  if (card.kind === "histogram" && card.minimum !== null && card.maximum !== null) {
    if (card.mean !== null && card.median !== null) {
      parts.push(
        `mean ${formatValue(card.mean, false)} · median ${formatValue(card.median, false)}`,
      );
    }
    if (card.minimum === card.maximum) {
      parts.push(`all ${formatValue(card.minimum, card.whole_values)}`);
    } else {
      const whole = card.whole_values;
      parts.push(
        `min ${formatValue(card.minimum, whole)} · max ${formatValue(card.maximum, whole)}`,
      );
    }
  }
  if (card.kind === "values") {
    parts.push(counted(card.distinct, { one: "value", many: "different values" }));
  }
  if (card.missing > 0) parts.push(`${card.missing.toLocaleString()} without a value`);
  return parts;
}

/** Why the bars of a card filter nothing: whose values they count, or that no column holds them. */
export function unfilteredReason(card: OverviewCard): string {
  if (card.subject === "record")
    return "No column of the explorer holds these values: a bar filters nothing.";
  return `Counted per ${SUBJECT_WORDS[card.subject].one}: a bar filters nothing.`;
}

/** When a statistic's card was computed, as a person reads a date; none for a card of no statistic. */
export function computedLabel(card: OverviewCard): string | null {
  if (!card.computed_at) return null;
  return `Computed ${new Date(card.computed_at).toLocaleString()}: later edits are not counted.`;
}

/** The cards in the overview's parts, in their order, those without a card left out. */
export function groupedCards(
  cards: OverviewCard[],
): { group: OverviewGroup; title: string; cards: OverviewCard[] }[] {
  return GROUP_ORDER.map((group) => ({
    group,
    title: GROUP_TITLES[group],
    cards: cards.filter((card) => card.group === group),
  })).filter((part) => part.cards.length > 0);
}

/** What the overview says it counts: "Overview of 1 record", "Overview of 12 of 60 records". */
export function overviewTitle(records: number, total: number): string {
  const kept =
    records === total
      ? records.toLocaleString()
      : `${records.toLocaleString()} of ${total.toLocaleString()}`;
  return `Overview of ${kept} ${total === 1 ? "record" : "records"}`;
}

/** The statistics a dataset has not computed, as a sentence names them. */
export function statisticNames(statistics: StatisticDefinition[]): string {
  return statistics.map((statistic) => statistic.label.toLowerCase()).join(", ");
}
