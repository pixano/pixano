/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadWorkspaceRecord } from "$lib/api/workspace";
import {
  annotations,
  entities,
  resetWorkspaceStores,
  saveData,
} from "$lib/stores/workspaceStores.svelte";
import { WorkspaceType } from "$lib/types/dataset";
import { commitLoadedWorkspace, forgetGoneAnnotation } from "$lib/utils/workspaceRuntimeMutations";

// An annotation a save found gone, taken off the screen, through the real loader and stores.

const DATASET_ID = "ds";
const RECORD_ID = "record-1";
const IMAGE_ID = "image-1";

const page = (items: unknown[]) => ({ items, total: items.length, limit: 1000, offset: 0 });
const jsonResponse = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200 });

const box = (id: string) => ({
  id,
  record_id: RECORD_ID,
  view_id: IMAGE_ID,
  entity_id: "dog",
  coords: [0.1, 0.1, 0.2, 0.2],
  format: "xywh",
  is_normalized: true,
  confidence: 0.8,
  source_type: "model",
  source_name: "detection",
  source_metadata: "{}",
  review_status: "pending",
  created_at: "",
  updated_at: "",
});

const fetchMock = vi.fn((url: string) => {
  const path = url.split("?")[0].slice(`/datasets/${DATASET_ID}/`.length);
  if (path === `records/${RECORD_ID}`) {
    return Promise.resolve(jsonResponse({ id: RECORD_ID, created_at: "", updated_at: "" }));
  }
  if (path === `records/${RECORD_ID}/images`) {
    const image = { id: IMAGE_ID, record_id: RECORD_ID, logical_name: "image", src: "" };
    return Promise.resolve(jsonResponse(page([image])));
  }
  if (path === "entities") {
    const dog = { id: "dog", record_id: RECORD_ID, parent_id: "", created_at: "", updated_at: "" };
    return Promise.resolve(jsonResponse(page([dog])));
  }
  if (path === "bboxes") return Promise.resolve(jsonResponse(page([box("gone"), box("kept")])));
  return Promise.resolve(jsonResponse(page([])));
});

beforeEach(async () => {
  vi.stubGlobal("fetch", fetchMock);
  resetWorkspaceStores();
  const { workspaceData } = await loadWorkspaceRecord(DATASET_ID, RECORD_ID, WorkspaceType.IMAGE, [
    "bboxes",
  ]);
  commitLoadedWorkspace(workspaceData, { main: {}, objects: {} });
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetWorkspaceStores();
});

describe("an annotation a save found gone", () => {
  it("leaves the screen and its entity's card, with nothing staged", () => {
    forgetGoneAnnotation("gone");

    expect(annotations.value.map((annotation) => annotation.id)).toEqual(["kept"]);
    expect(entities.value[0].ui.childs?.map((annotation) => annotation.id)).toEqual(["kept"]);
    expect(saveData.value).toEqual([]);
  });

  it("changes nothing when the screen does not show it", () => {
    const shown = annotations.value;

    forgetGoneAnnotation("never-shown");

    expect(annotations.value).toBe(shown);
  });
});
