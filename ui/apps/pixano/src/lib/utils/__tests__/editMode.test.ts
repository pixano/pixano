/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

type AnnotationStub = { id: string; ui: { displayControl: { editing?: boolean } } };

const mocks = vi.hoisted(() => {
  const annotations = {
    value: [] as AnnotationStub[],
    update: vi.fn((updater: (current: AnnotationStub[]) => AnnotationStub[]) => {
      annotations.value = updater(annotations.value);
    }),
  };
  const editedTrackletId = { value: null as string | null };
  return {
    annotations,
    editedTrackletId,
    clearTrackEditing: () => {
      editedTrackletId.value = null;
    },
  };
});

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  annotations: mocks.annotations,
  clearTrackEditing: mocks.clearTrackEditing,
  editedTrackletId: mocks.editedTrackletId,
  highlightedEntity: { value: null },
  mediaViews: { value: {} },
  selectedTool: { value: { type: "PAN" } },
  trackletIdByChildId: { value: new Map<string, string>() },
}));
vi.mock("$lib/stores/trackingStore.svelte", () => ({
  isTracking: { value: false },
  isVosSessionActive: { value: false },
}));
vi.mock("$lib/stores/trackingByDetectionStore.svelte", () => ({
  isTrackingByDetectionActive: { value: false },
}));
vi.mock("$lib/tools", () => ({
  panTool: { type: "PAN" },
  ToolType: { Pan: "PAN", Fusion: "FUSION" },
}));
vi.mock("$lib/utils/entityLookupUtils", () => ({ tryGetTopEntity: () => null }));
vi.mock("$lib/utils/highlightOperations", () => ({ highlightEntity: vi.fn() }));

function annotation(id: string, editing: boolean): AnnotationStub {
  return { id, ui: { displayControl: { editing } } };
}

describe("exitEditMode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.editedTrackletId.value = null;
    mocks.annotations.value = [];
  });

  it("reports that nothing was being edited, and changes nothing", async () => {
    const { exitEditMode } = await import("$lib/utils/editMode");
    mocks.annotations.value = [annotation("box", false)];

    expect(exitEditMode()).toBe(false);
    expect(mocks.annotations.update).not.toHaveBeenCalled();
  });

  it("ends a track's edit mode and reports it", async () => {
    const { exitEditMode } = await import("$lib/utils/editMode");
    mocks.editedTrackletId.value = "track";
    mocks.annotations.value = [annotation("keyframe", false)];

    expect(exitEditMode()).toBe(true);
    expect(mocks.editedTrackletId.value).toBeNull();
  });

  it("clears an annotation's editing flag and reports it", async () => {
    const { exitEditMode } = await import("$lib/utils/editMode");
    mocks.annotations.value = [annotation("box", true), annotation("other", false)];

    expect(exitEditMode()).toBe(true);
    expect(mocks.annotations.value.map((stub) => stub.ui.displayControl.editing)).toEqual([
      false,
      false,
    ]);
  });
});
