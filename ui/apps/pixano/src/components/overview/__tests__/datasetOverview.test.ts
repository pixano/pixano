/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { render } from "svelte/server";
import { describe, expect, it } from "vitest";

import DatasetOverview from "../DatasetOverview.svelte";
import type { DatasetOverview as Overview } from "$lib/api/overviewApi";
import type { StatisticDefinition } from "$lib/api/statisticsApi";

// What the overview says of itself, rendered as the server renders it: these tests read the
// markup, not a click.

const noop = () => {};

const OBJECTS: StatisticDefinition = {
  name: "entity_count",
  level: "record",
  choices: { level: "record", element: "entity", measure: "count" },
  label: "Number of objects",
  description: "",
  unit: "",
  value_type: "int",
  version: 1,
  created_at: "2026-11-13T00:00:00Z",
};
const BOXES: StatisticDefinition = {
  ...OBJECTS,
  name: "bbox_count",
  choices: { level: "record", element: "bbox", measure: "count" },
  label: "Number of boxes",
};

const WITHOUT_STATISTICS: Overview = {
  records: 60,
  total_records: 60,
  splits: ["train", "validation"],
  cards: [],
  statistics_to_compute: [OBJECTS, BOXES],
};

type Shown = {
  overview?: Overview | null;
  error?: string;
  loading?: boolean;
  statisticsJobRuns?: boolean | null;
  readingAgain?: boolean;
};

const overviewMarkup = ({
  overview = WITHOUT_STATISTICS,
  error = "",
  loading = false,
  statisticsJobRuns = true,
  readingAgain = false,
}: Shown = {}): string =>
  render(DatasetOverview, {
    props: {
      overview,
      error,
      kept: {},
      bySplit: false,
      loading,
      statisticsJobRuns,
      readingAgain,
      onToggleSplit: noop,
      onBarClick: noop,
      onClear: noop,
      onReadAgain: noop,
    },
  }).body;

/** The text a person reads, tags and the spacing between them dropped. */
const text = (markup: string): string =>
  markup
    .replace(/<!--.*?-->/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/** The opening tag of the button whose text is this; empty when there is none. */
const buttonNamed = (markup: string, name: string): string =>
  [...markup.matchAll(/(<button[^>]*>)([\s\S]*?)<\/button>/g)].find(
    ([, , content]) => text(content) === name,
  )?.[1] ?? "";

/** Whether an opening tag carries the disabled attribute, not a class naming it. */
const isDisabled = (openingTag: string): boolean => /\sdisabled(?:=""|(?=[\s>]))/.test(openingTag);

describe("the statistics the overview waits for", () => {
  it("are named, with Read again where their job can run, and nothing to compute them", () => {
    const markup = overviewMarkup();

    expect(text(markup)).toContain("Not computed yet: number of objects, number of boxes.");
    expect(text(markup)).toContain("this interface cannot start that job yet");
    expect(buttonNamed(markup, "Read again")).not.toBe("");
    expect(isDisabled(buttonNamed(markup, "Read again"))).toBe(false);
    expect(text(markup)).not.toContain("Compute");
  });

  it("say where they are computed, and offer nothing to click, where their job cannot run", () => {
    const markup = overviewMarkup({ statisticsJobRuns: false });

    expect(text(markup)).toContain(
      "The statistics job computes them, where pixano-worker runs it.",
    );
    expect(buttonNamed(markup, "Read again")).toBe("");
  });

  it("are only named until the server says whether their job can run", () => {
    const markup = overviewMarkup({ statisticsJobRuns: null });

    expect(text(markup)).toContain("Not computed yet: number of objects, number of boxes.");
    expect(text(markup)).not.toContain("pixano-worker");
    expect(buttonNamed(markup, "Read again")).toBe("");
  });

  it("are not mentioned once computed", () => {
    expect(
      text(overviewMarkup({ overview: { ...WITHOUT_STATISTICS, statistics_to_compute: [] } })),
    ).not.toContain("Not computed yet");
  });
});

describe("reading the overview again", () => {
  it("waits for the reading under way, and says it reads", () => {
    const markup = overviewMarkup({ readingAgain: true });

    expect(isDisabled(buttonNamed(markup, "Reading…"))).toBe(true);
  });

  it("waits for the filters a person changed to be read", () => {
    expect(isDisabled(buttonNamed(overviewMarkup({ loading: true }), "Read again"))).toBe(true);
  });

  it("is offered when the overview could not be read, with the server's words", () => {
    const markup = overviewMarkup({ overview: null, error: "The dataset is being written." });

    expect(text(markup)).toContain("The dataset is being written.");
    expect(isDisabled(buttonNamed(markup, "Try again"))).toBe(false);
  });
});
