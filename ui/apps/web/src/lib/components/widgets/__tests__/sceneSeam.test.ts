/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildSeam } from "../sceneSeam.js";
import {
  AnnotationCollection,
  type BBox3DGeometry,
} from "$lib/annotations/annotationCollection.svelte.js";
import type { LiveAnnotationDraft } from "$lib/annotations/scene/sceneContext.js";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

const GEOMETRY: BBox3DGeometry = { coords: [0, 0, 0, 1, 1, 1], format: "xyzwhd" };

/** Only the slice of the manager `buildSeam` actually touches. */
function fakeManager() {
  let liveDraft: LiveAnnotationDraft | null = null;
  return {
    annotations: new AnnotationCollection(),
    entities: [],
    pendingMutations: [],
    get liveDraft() {
      return liveDraft;
    },
    setLiveDraft: (draft: LiveAnnotationDraft | null) => (liveDraft = draft),
    queueMutation: () => {},
    upsertUpdateMutation: () => {},
    patchPendingCreateMutation: () => {},
    dropMutationsForLocalAnnotation: () => {},
    beginPendingAnnotation: () => {},
    isEntityVisible: () => true,
  };
}

function seamFor(manager: ReturnType<typeof fakeManager>, widgetId: string) {
  return buildSeam(manager as unknown as WorkspaceManager, {
    widgetId,
    buildContext: { datasetId: "ds", recordId: "rec", viewId: "v1" },
    storage: { activeToolId: "select" },
  });
}

// The live-draft slot is shared workspace-wide, so these rules are what stop one
// widget's tool from wiping a gesture running in another. They live in the seam
// rather than in each tool precisely so a tool author cannot get them wrong.
describe("buildSeam — live-draft ownership", () => {
  it("stamps the publishing widget's id, so a tool cannot forge another's", () => {
    const manager = fakeManager();

    seamFor(manager, "widget-a").liveDraft.publish({
      kind: "bbox3d",
      geometry: GEOMETRY,
      editingId: null,
    });

    expect(manager.liveDraft).toEqual({
      kind: "bbox3d",
      geometry: GEOMETRY,
      editingId: null,
      sourceWidgetId: "widget-a",
    });
  });

  it("clears a draft the widget published itself", () => {
    const manager = fakeManager();
    const seam = seamFor(manager, "widget-a");

    seam.liveDraft.publish({ kind: "bbox3d", geometry: GEOMETRY, editingId: null });
    seam.liveDraft.clear();

    expect(manager.liveDraft).toBeNull();
  });

  it("leaves another widget's in-flight gesture untouched", () => {
    const manager = fakeManager();
    seamFor(manager, "widget-a").liveDraft.publish({
      kind: "bbox3d",
      geometry: GEOMETRY,
      editingId: null,
    });

    // B idles/unmounts and clears — A is mid-gesture and must survive it.
    seamFor(manager, "widget-b").liveDraft.clear();

    expect(manager.liveDraft?.sourceWidgetId).toBe("widget-a");
  });

  it("clearing an already-empty slot is a no-op", () => {
    const manager = fakeManager();

    seamFor(manager, "widget-a").liveDraft.clear();

    expect(manager.liveDraft).toBeNull();
  });

  it("exposes the shared slot for reading regardless of which widget published", () => {
    const manager = fakeManager();
    const a = seamFor(manager, "widget-a");
    const b = seamFor(manager, "widget-b");

    a.liveDraft.publish({ kind: "bbox3d", geometry: GEOMETRY, editingId: "box-1" });

    // B observes A's gesture — that is the whole point of the slot.
    expect(b.liveDraft.get()?.editingId).toBe("box-1");
    expect(b.liveDraft.get()?.sourceWidgetId).toBe("widget-a");
  });
});
