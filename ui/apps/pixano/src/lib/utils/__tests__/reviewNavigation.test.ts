/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import type { NextRecordToReview } from "$lib/api/restTypes";
import {
  recordsLeftText,
  saveAndOpenNext,
  type ReviewNavigationPorts,
} from "$lib/utils/reviewNavigation";
import { getReviewRoute, getWorkspaceRoute, isReviewRoute } from "$lib/utils/routes";

/** The ports of a workspace whose save does as told, and whose queue answers `next`. */
function ports(
  saved: boolean,
  next: NextRecordToReview,
): ReviewNavigationPorts & { steps: string[]; stillOpen: boolean } {
  const steps: string[] = [];
  const workspace = {
    steps,
    stillOpen: true,
    save: vi.fn(() => {
      steps.push("save");
      return Promise.resolve(saved);
    }),
    nextAfter: vi.fn((recordId: string) => {
      steps.push(`next after ${recordId}`);
      return Promise.resolve(next);
    }),
    isStillOpen: vi.fn(() => workspace.stillOpen),
    open: vi.fn((recordId: string) => {
      steps.push(`open ${recordId}`);
      return Promise.resolve();
    }),
  };
  return workspace;
}

describe("Save & next", () => {
  it("saves the record, then opens the next one the dataset holds to review", async () => {
    const workspace = ports(true, { record_id: "record-2", remaining: 4 });

    const outcome = await saveAndOpenNext("record-1", workspace);

    expect(workspace.steps).toEqual(["save", "next after record-1", "open record-2"]);
    expect(outcome).toEqual({ kind: "opened", recordId: "record-2", remaining: 4 });
  });

  it("stays on a record whose save failed, with its changes", async () => {
    const workspace = ports(false, { record_id: "record-2", remaining: 4 });

    expect(await saveAndOpenNext("record-1", workspace)).toEqual({ kind: "not-saved" });
    expect(workspace.steps).toEqual(["save"]);
  });

  it("stays when nothing is left to review", async () => {
    const workspace = ports(true, { record_id: null, remaining: 0 });

    expect(await saveAndOpenNext("record-1", workspace)).toEqual({ kind: "done" });
    expect(workspace.open).not.toHaveBeenCalled();
  });

  it("stays on the only record left to review", async () => {
    // What is left on it may be hidden: the queue wraps round to it.
    const workspace = ports(true, { record_id: "record-1", remaining: 1 });

    expect(await saveAndOpenNext("record-1", workspace)).toEqual({ kind: "last" });
    expect(workspace.open).not.toHaveBeenCalled();
  });

  it("says the queue cannot be read, the record saved and still open", async () => {
    const workspace = ports(true, { record_id: "record-2", remaining: 4 });
    workspace.nextAfter = () => Promise.reject(new Error("503"));

    expect(await saveAndOpenNext("record-1", workspace)).toEqual({ kind: "queue-unreadable" });
    expect(workspace.save).toHaveBeenCalled();
    expect(workspace.open).not.toHaveBeenCalled();
  });

  it("moves nobody when the reviewer opened another record meanwhile", async () => {
    const workspace = ports(true, { record_id: "record-2", remaining: 4 });
    workspace.stillOpen = false;

    expect(await saveAndOpenNext("record-1", workspace)).toEqual({ kind: "left" });
    expect(workspace.open).not.toHaveBeenCalled();
  });
});

describe("the records left to review", () => {
  it.each([
    [{ record_id: "record-2", remaining: 12 }, "12 records to review"],
    [{ record_id: "record-2", remaining: 1 }, "1 record to review"],
    [{ record_id: "record-1", remaining: 1 }, "Only this record is left to review"],
    [{ record_id: null, remaining: 0 }, "All records reviewed"],
  ])("as the queue answers %j for record-1: %s", (queue, text) => {
    expect(recordsLeftText(queue, "record-1")).toBe(text);
  });

  it("say nothing before the queue answers", () => {
    expect(recordsLeftText(null, "record-1")).toBe("");
  });
});

describe("the route of a record opened in review", () => {
  const url = (route: string) => new URL(`http://localhost/${route}`);

  it("opens the record in review, with no explorer query", () => {
    const route = getReviewRoute("ds", "record-1");

    expect(route).toBe("#/explorer/ds/workspace/record-1?review=pending");
    expect(isReviewRoute(url(route))).toBe(true);
  });

  it("is not the route of a record opened from the explorer", () => {
    expect(isReviewRoute(url(getWorkspaceRoute("ds", "record-1", "filter=split%3Dtrain")))).toBe(
      false,
    );
    expect(isReviewRoute(url(getWorkspaceRoute("ds", "record-1")))).toBe(false);
  });
});
