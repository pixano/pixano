/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  allDistinct,
  barKept,
  barLabel,
  cardChart,
  cardSummary,
  computedLabel,
  filtersAfterClick,
  filtersForBar,
  filtersForValue,
  filtersWithoutCard,
  formatShare,
  formatValue,
  groupedCards,
  itemCount,
  keptBars,
  MAX_FILTER_VALUE_LENGTH,
  MAX_FILTERS,
  NO_SPLIT_LABEL,
  NOTABLE_SPLIT_GAP,
  notableExplanation,
  OTHERS_LABEL,
  overviewTitle,
  SPLIT_CARD_ID,
  splitLabel,
  statisticNames,
  unfilteredReason,
  withColumnFilters,
  withinFilterLimit,
} from "../overview";
import type { OverviewCard } from "$lib/api/overviewApi";
import type { StatisticDefinition } from "$lib/api/statisticsApi";

function card(changes: Partial<OverviewCard>): OverviewCard {
  return {
    id: "statistic:entity_count",
    group: "annotations",
    label: "Number of objects",
    unit: "",
    subject: "record",
    kind: "histogram",
    population: 4,
    missing: 0,
    counted_by_split: {},
    filter_column: "record_statistics.entity_count",
    whole_values: true,
    minimum: 0,
    maximum: 2,
    mean: 1,
    median: 1,
    bars: [
      { start: 0, end: 1, count: 1, by_split: { test: 1 } },
      { start: 1, end: 2, count: 2, by_split: { train: 1, val: 1 } },
      { start: 2, end: 3, count: 1, by_split: { train: 1 } },
    ],
    values: [],
    distinct: 0,
    others: 0,
    others_by_split: {},
    ...changes,
  };
}

const CLASSES = card({
  id: "object:class",
  label: "Objects per class",
  subject: "object",
  kind: "values",
  filter_column: null,
  whole_values: false,
  minimum: null,
  maximum: null,
  mean: null,
  median: null,
  bars: [],
  values: [
    { value: "dog", count: 2, by_split: { train: 2 } },
    { value: "bird", count: 1, by_split: { val: 1 } },
  ],
  distinct: 3,
  others: 1,
  others_by_split: { train: 1 },
  counted_by_split: { train: 3, val: 1 },
});

const WEATHER = card({
  id: "field:weather",
  group: "records",
  label: "Weather",
  kind: "values",
  filter_column: "weather",
  whole_values: false,
  bars: [],
  values: [
    { value: "rain", count: 2, by_split: {} },
    { value: "sun", count: 1, by_split: {} },
  ],
  distinct: 2,
});

describe("formatValue and barLabel", () => {
  it("writes whole numbers whole, others as a statistic's column writes them", () => {
    expect([
      formatValue(2.6, true),
      formatValue(1234.5, false),
      formatValue(0.12345, false),
    ]).toEqual(["3", "1,234.5", "0.123"]);
  });

  it("names a bar by its whole value, its range of whole values, or its range", () => {
    expect(barLabel({ start: 2, end: 3, count: 0, by_split: {} }, true)).toBe("2");
    expect(barLabel({ start: 320, end: 337, count: 0, by_split: {} }, true)).toBe("320–336");
    expect(barLabel({ start: 0.1, end: 0.2, count: 0, by_split: {} }, false)).toBe("0.1–0.2");
    expect(barLabel({ start: 0.25, end: 0.25, count: 3, by_split: {} }, false)).toBe("0.25");
  });

  it("names the split of a record that names none", () => {
    expect([splitLabel(""), splitLabel("train")]).toEqual([NO_SPLIT_LABEL, "train"]);
  });
});

describe("filtersForBar and filtersForValue", () => {
  it("keeps the records of a whole value, or of a range of them", () => {
    expect(filtersForBar(card({}), 1)).toEqual(["record_statistics.entity_count:eq:1"]);
    const wide = card({ bars: [{ start: 320, end: 337, count: 1, by_split: {} }] });
    expect(filtersForBar(wide, 0)).toEqual([
      "record_statistics.entity_count:gte:320",
      "record_statistics.entity_count:lte:336",
    ]);
  });

  it("keeps the end of the last bar of decimals, and leaves out the end of the others", () => {
    const decimals = card({
      whole_values: false,
      filter_column: "score",
      bars: [
        { start: 0, end: 0.5, count: 1, by_split: {} },
        { start: 0.5, end: 1, count: 1, by_split: {} },
      ],
    });

    expect(filtersForBar(decimals, 0)).toEqual(["score:gte:0", "score:lt:0.5"]);
    expect(filtersForBar(decimals, 1)).toEqual(["score:gte:0.5", "score:lte:1"]);
  });

  it("keeps the records holding a value", () => {
    expect(filtersForValue(WEATHER, 0)).toEqual(["weather:eq:rain"]);
  });

  it("filters nothing on what is not the records' own, on the others, nor on a value too long to send", () => {
    expect(filtersForValue(CLASSES, 0)).toBeNull();
    expect(filtersForBar(card({ filter_column: null }), 0)).toBeNull();
    expect(filtersForValue(WEATHER, 2)).toBeNull();
    const long = card({
      ...WEATHER,
      values: [{ value: "x".repeat(MAX_FILTER_VALUE_LENGTH + 1), count: 1, by_split: {} }],
    });
    expect(filtersForValue(long, 0)).toBeNull();
  });

  it("replaces the filters on a column, the others kept", () => {
    const filters = ["split:eq:train", "record_statistics.entity_count:eq:1", "rank:gte:2"];

    expect(
      withColumnFilters(filters, "record_statistics.entity_count", [
        "record_statistics.entity_count:eq:2",
      ]),
    ).toEqual(["split:eq:train", "rank:gte:2", "record_statistics.entity_count:eq:2"]);
  });
});

describe("filtersAfterClick and filtersWithoutCard", () => {
  it("keeps the records of the bar clicked, in place of the card's own filters", () => {
    const filters = ["split:eq:train", "record_statistics.entity_count:eq:2"];

    expect(filtersAfterClick(filters, card({}), 1)).toEqual([
      "split:eq:train",
      "record_statistics.entity_count:eq:1",
    ]);
  });

  it("drops the card's own filters when the bar they keep is clicked again", () => {
    const filters = ["split:eq:train", "record_statistics.entity_count:eq:1"];

    expect(filtersAfterClick(filters, card({}), 1)).toEqual(["split:eq:train"]);
  });

  it("does nothing for a bar that filters nothing", () => {
    expect(filtersAfterClick([], CLASSES, 0)).toBeNull();
  });

  it("tells the bar whose records the card's own filters keep alone", () => {
    const filters = ["split:eq:train", "record_statistics.entity_count:eq:1"];

    expect([0, 1, 2].map((index) => barKept(filters, card({}), index))).toEqual([
      false,
      true,
      false,
    ]);
    expect(barKept(["record_statistics.entity_count:gte:1"], card({}), 1)).toBe(false);
    expect(barKept([], CLASSES, 0)).toBe(false);
  });

  it("tells, for every card, the bars the filters keep alone", () => {
    const filters = ["record_statistics.entity_count:eq:2", "weather:eq:sun"];

    expect(keptBars([card({}), WEATHER, CLASSES], filters)).toEqual({
      "statistic:entity_count": [false, false, true],
      "field:weather": [false, true],
      "object:class": [false, false, false],
    });
    expect([itemCount(card({})), itemCount(WEATHER), itemCount(CLASSES)]).toEqual([3, 2, 3]);
  });

  it("clears the card's own filters, the others kept", () => {
    const filters = ["weather:eq:rain", "split:eq:train"];

    expect(filtersWithoutCard(filters, WEATHER)).toEqual(["split:eq:train"]);
    expect(filtersWithoutCard(filters, CLASSES)).toEqual(filters);
  });

  it("tells the filters the server takes from those past its limit", () => {
    const filters = Array.from({ length: MAX_FILTERS }, (_unused, index) => `rank:gte:${index}`);

    expect([withinFilterLimit(filters), withinFilterLimit([...filters, "split:eq:val"])]).toEqual([
      true,
      false,
    ]);
  });
});

describe("cardChart", () => {
  it("draws the counts when the splits are not compared", () => {
    expect(cardChart(card({}), [])).toEqual({
      labels: ["0", "1", "2"],
      counts: [1, 2, 1],
      series: [{ label: "", values: [1, 2, 1], colorIndex: 0 }],
      shares: false,
      notable: [false, false, false],
      clickable: [true, true, true],
      selected: [false, false, false],
    });
  });

  it("draws each split's share of its own values, and points out where they differ", () => {
    const objects = card({ counted_by_split: { test: 1, train: 2, val: 1 } });

    const chart = cardChart(objects, ["test", "train", "val"]);

    expect(chart.shares).toBe(true);
    expect(chart.series).toEqual([
      { label: "test", values: [1, 0, 0], colorIndex: 0 },
      { label: "train", values: [0, 0.5, 0.5], colorIndex: 1 },
      { label: "val", values: [0, 1, 0], colorIndex: 2 },
    ]);
    expect(chart.notable).toEqual([true, true, true]);
  });

  it("keeps a split's color from the overview's splits, whichever splits a card holds", () => {
    const series = cardChart(CLASSES, ["test", "train", "val"]).series;

    expect(series.map((one) => [one.label, one.colorIndex])).toEqual([
      ["train", 1],
      ["val", 2],
    ]);
  });

  it("counts the values not listed together, and points out a value one split holds and another none", () => {
    const chart = cardChart(CLASSES, ["train", "val"]);

    expect(chart.labels).toEqual(["dog", "bird", OTHERS_LABEL]);
    expect(chart.series.map((one) => one.values)).toEqual([
      [2 / 3, 0, 1 / 3],
      [0, 1, 0],
    ]);
    expect(chart.notable).toEqual([true, true, true]);
  });

  it("points out a gap of a tenth exactly, which the arithmetic of shares puts a hair below", () => {
    // 0.3 - 0.2 is 0.09999999999999998 in floating point.
    const gap = card({
      counted_by_split: { train: 10, val: 10 },
      bars: [
        { start: 0, end: 1, count: 5, by_split: { train: 3, val: 2 } },
        { start: 1, end: 2, count: 15, by_split: { train: 7, val: 8 } },
      ],
    });

    expect(0.3 - 0.2 < NOTABLE_SPLIT_GAP).toBe(true);
    expect(cardChart(gap, ["train", "val"]).notable).toEqual([true, true]);
  });

  it("points out nothing where the splits' shares are alike", () => {
    const alike = card({
      counted_by_split: { train: 10, val: 10 },
      bars: [{ start: 0, end: 1, count: 20, by_split: { train: 10, val: 10 } }],
    });

    expect(cardChart(alike, ["train", "val"]).notable).toEqual([false]);
  });

  it("compares only the splits holding a value of the card", () => {
    expect(cardChart(CLASSES, ["test", "train", "val"]).series.map((one) => one.label)).toEqual([
      "train",
      "val",
    ]);
    expect(cardChart(CLASSES, ["train"]).shares).toBe(false);
  });

  it("never compares the split card with itself", () => {
    const split = card({
      ...WEATHER,
      id: SPLIT_CARD_ID,
      filter_column: "split",
      values: [
        { value: "train", count: 2, by_split: { train: 2 } },
        { value: "val", count: 1, by_split: { val: 1 } },
      ],
      counted_by_split: { train: 2, val: 1 },
    });

    expect(cardChart(split, ["train", "val"]).shares).toBe(false);
  });

  it("marks the bars whose records the card's own filters keep, the others still drawn", () => {
    const filtered = card({
      filtered: true,
      bars: [
        { start: 0, end: 1, count: 1, selected: 0, by_split: {} },
        { start: 1, end: 2, count: 2, selected: 0, by_split: {} },
        { start: 2, end: 3, count: 1, selected: 1, by_split: {} },
      ],
    });

    expect(cardChart(filtered, []).selected).toEqual([false, false, true]);
  });

  it("marks the others when the card's own filters keep some of them", () => {
    const filtered = card({
      ...WEATHER,
      filtered: true,
      values: [{ value: "rain", count: 2, selected: 0, by_split: {} }],
      others: 1,
      others_selected: 1,
    });

    expect(cardChart(filtered, [])).toMatchObject({
      labels: ["rain", OTHERS_LABEL],
      clickable: [true, false],
      selected: [false, true],
    });
  });
});

describe("cardSummary and what a card says", () => {
  it("says how many, their summary and those missing", () => {
    expect(cardSummary(card({ missing: 1, population: 5 }))).toEqual([
      "4 records",
      "mean 1 · median 1",
      "min 0 · max 2",
      "1 without a value",
    ]);
  });

  it("says how many values a card of values counts, one value in the singular", () => {
    expect(cardSummary(CLASSES)).toEqual(["4 objects", "3 different values"]);
    expect(cardSummary(card({ ...WEATHER, population: 1, distinct: 1 }))).toEqual([
      "1 record",
      "1 value",
    ]);
  });

  it("says a single value once rather than as a smallest and a largest", () => {
    const one = card({
      minimum: 0.25,
      maximum: 0.25,
      mean: 0.25,
      median: 0.25,
      whole_values: false,
    });

    expect(cardSummary(one)).toContain("all 0.25");
  });

  it("says when none holds a value, and when there is none to count", () => {
    expect(cardSummary(card({ population: 1, missing: 1 }))).toEqual(["The record holds no value"]);
    expect(cardSummary(card({ population: 3, missing: 3 }))).toEqual([
      "None of the 3 records holds a value",
    ]);
    expect(cardSummary(card({ population: 0 }))).toEqual(["No records"]);
  });

  it("tells a card whose every value differs, more than it lists: an identifier, a free text", () => {
    expect(allDistinct(card({ ...WEATHER, population: 30, distinct: 30, others: 10 }))).toBe(true);
    expect(allDistinct(WEATHER)).toBe(false);
  });

  it("still draws a few values held once each, those of three records in three splits", () => {
    expect(allDistinct(card({ ...WEATHER, population: 3, missing: 0, distinct: 3 }))).toBe(false);
  });

  it("writes a share as a percentage, and says what an outline means", () => {
    expect(formatShare(0.125)).toBe("12.5%");
    expect(notableExplanation()).toContain(`${NOTABLE_SPLIT_GAP * 100} points`);
  });

  it("says why a card's bars filter nothing", () => {
    expect(unfilteredReason(CLASSES)).toBe("Counted per object: a bar filters nothing.");
    expect(unfilteredReason(card({ filter_column: null }))).toContain("No column of the explorer");
  });

  it("dates a statistic's card, and no other", () => {
    expect(computedLabel(card({ computed_at: "2026-11-10T09:00:00Z" }))).toMatch(/^Computed /);
    expect(computedLabel(WEATHER)).toBeNull();
  });
});

describe("groupedCards, overviewTitle and statisticNames", () => {
  it("puts the cards in the overview's parts, those without a card left out", () => {
    const field = card({ id: "field:split", group: "records", kind: "values", distinct: 3 });

    expect(
      groupedCards([CLASSES, field]).map((part) => [part.title, part.cards.map((one) => one.id)]),
    ).toEqual([
      ["Records", ["field:split"]],
      ["Annotations", ["object:class"]],
    ]);
  });

  it("says how many records it counts, of how many", () => {
    expect([overviewTitle(4, 4), overviewTitle(1, 4), overviewTitle(1, 1)]).toEqual([
      "Overview of 4 records",
      "Overview of 1 of 4 records",
      "Overview of 1 record",
    ]);
  });

  it("names the statistics to compute in a sentence", () => {
    const statistics = [{ label: "Number of objects" }, { label: "Number of boxes" }];

    expect(statisticNames(statistics as StatisticDefinition[])).toBe(
      "number of objects, number of boxes",
    );
  });
});
