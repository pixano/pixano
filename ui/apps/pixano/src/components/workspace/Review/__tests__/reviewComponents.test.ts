/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { render } from "svelte/server";
import { describe, expect, it } from "vitest";

import ReviewBar from "../ReviewBar.svelte";
import ReviewStatusStrip from "../ReviewStatusStrip.svelte";
import { REVIEW_STATUS } from "$lib/constants/reviewConstants";
import type { ReviewSummary } from "$lib/utils/reviewStatus";

// What the review's components show, rendered as the server renders them: these tests read the
// markup, not a click.

const noop = () => {};

const PENDING: ReviewSummary = {
  status: REVIEW_STATUS.PENDING,
  pendingCount: 1,
  hiddenCount: 0,
  unsaved: false,
  model: "yolo26n",
  score: 0.873,
};

const strip = (summary: ReviewSummary, canDecide = true): string =>
  render(ReviewStatusStrip, {
    props: { summary, scope: "object", canDecide, onAccept: noop, onReject: noop },
  }).body;

/** The text a person reads, tags and the spacing between them dropped. */
const text = (markup: string): string =>
  markup
    .replace(/<!--.*?-->/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/** The opening tag of the button whose text is this. */
const buttonNamed = (markup: string, name: string): string =>
  [...markup.matchAll(/(<button[^>]*>)([\s\S]*?)<\/button>/g)].find(
    ([, , content]) => text(content) === name,
  )?.[1] ?? "";

/** Whether an opening tag carries the disabled attribute, not a class naming it. */
const isDisabled = (openingTag: string): boolean => /\sdisabled(?:=""|(?=[\s>]))/.test(openingTag);

describe("the review strip", () => {
  it("shows a proposal still to review with its model, its score, Accept and Reject", () => {
    expect(text(strip(PENDING))).toBe("Pending review yolo26n 87.3% Accept Reject");
  });

  it("counts an object's proposals still to review", () => {
    expect(text(strip({ ...PENDING, pendingCount: 2 }))).toContain("Pending review · 2");
  });

  it("says how many of them are hidden, which stay to review", () => {
    expect(text(strip({ ...PENDING, pendingCount: 2, hiddenCount: 1 }))).toContain("· 1 hidden");
  });

  it("offers no decision where none can be taken", () => {
    expect(text(strip(PENDING, false))).toBe("Pending review yolo26n 87.3%");
  });

  it("shows an accepted proposal without Accept or Reject", () => {
    const accepted = { ...PENDING, status: REVIEW_STATUS.ACCEPTED, pendingCount: 0 };

    expect(text(strip(accepted))).toBe("Accepted yolo26n 87.3%");
  });

  it("says an Accept is not saved yet", () => {
    const unsaved = { ...PENDING, status: REVIEW_STATUS.ACCEPTED, pendingCount: 0, unsaved: true };

    expect(text(strip(unsaved))).toContain("Accepted, not saved");
  });

  it("leaves out a model and a score it does not know", () => {
    expect(text(strip({ ...PENDING, model: null, score: null }))).toBe(
      "Pending review Accept Reject",
    );
  });
});

describe("the review bar", () => {
  const bar = (pendingCount: number, shownPendingCount: number, canDecide = true): string =>
    render(ReviewBar, {
      props: {
        active: true,
        pendingCount,
        shownPendingCount,
        canDecide,
        onActiveChange: noop,
        onAcceptAll: noop,
      },
    }).body;

  it("says how much of the record is left to review", () => {
    expect(text(bar(3, 3))).toBe("Review 3 left on this record Accept all");
  });

  it("says how much of it is hidden, which Accept all leaves", () => {
    expect(text(bar(3, 1))).toContain("3 left on this record (2 hidden)");
  });

  it("says when nothing is left on the record", () => {
    expect(text(bar(0, 0))).toContain("Nothing left on this record");
  });

  it("offers Accept all only while a proposal to review is shown and a decision can be taken", () => {
    expect(isDisabled(buttonNamed(bar(2, 1), "Accept all"))).toBe(false);
    expect(isDisabled(buttonNamed(bar(2, 0), "Accept all"))).toBe(true);
    expect(isDisabled(buttonNamed(bar(2, 1, false), "Accept all"))).toBe(true);
  });
});
