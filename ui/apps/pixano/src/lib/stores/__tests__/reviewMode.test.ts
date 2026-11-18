/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadWorkspaceRecord } from "$lib/api/workspace";
import {
  highlightedEntity,
  resetWorkspaceStores,
  reviewModeIsActive,
} from "$lib/stores/workspaceStores.svelte";
import { WorkspaceType } from "$lib/types/dataset";
import { commitLoadedWorkspace } from "$lib/utils/workspaceRuntimeMutations";

// How long the review mode lasts: from record to record while the workspace stays open, as a
// reviewer goes from one to the next, and no longer.

const DATASET_ID = "ds";

const page = (items: unknown[]) => ({ items, total: items.length, limit: 1000, offset: 0 });
const jsonResponse = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200 });

const fetchMock = vi.fn((url: string) => {
  const path = url.split("?")[0].slice(`/datasets/${DATASET_ID}/`.length);
  if (/^records\/[^/]+$/.test(path)) {
    return Promise.resolve(
      jsonResponse({ id: path.split("/")[1], created_at: "", updated_at: "" }),
    );
  }
  return Promise.resolve(jsonResponse(page([])));
});

async function openRecord(recordId: string): Promise<void> {
  const { workspaceData } = await loadWorkspaceRecord(DATASET_ID, recordId, WorkspaceType.IMAGE, [
    "bboxes",
  ]);
  commitLoadedWorkspace(workspaceData, { main: {}, objects: {} });
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  resetWorkspaceStores();
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetWorkspaceStores();
});

describe("the review mode", () => {
  it("is off when the workspace opens", () => {
    expect(reviewModeIsActive.value).toBe(false);
  });

  it("lasts from record to record", async () => {
    await openRecord("record-1");
    reviewModeIsActive.value = true;

    await openRecord("record-2");

    expect(reviewModeIsActive.value).toBe(true);
  });

  it("ends with the workspace", async () => {
    await openRecord("record-1");
    reviewModeIsActive.value = true;

    resetWorkspaceStores();

    expect(reviewModeIsActive.value).toBe(false);
  });
});

describe("the next record", () => {
  it("opens with no object focused, so that none of its annotations is faded", async () => {
    // The focus named an object of the record left: kept, it faded every annotation of the
    // record opened next.
    await openRecord("record-1");
    highlightedEntity.value = "an-object-of-record-1";

    await openRecord("record-2");

    expect(highlightedEntity.value).toBeNull();
  });
});
