/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadWorkspaceRecord } from "$lib/api/workspace";
import { REVIEW_STATUS } from "$lib/constants/reviewConstants";
import {
  annotations,
  entities,
  highlightedEntity,
  resetWorkspaceStores,
  reviewedAnnotation,
  reviewModeIsActive,
  saveData,
  selectedTool,
} from "$lib/stores/workspaceStores.svelte";
import { fusionTool, rectangleTool, ToolType } from "$lib/tools";
import { WorkspaceType, type Annotation, type Entity } from "$lib/types/dataset";
import { ShapeType, type Shape } from "$lib/types/shapeTypes";
import { applyNewShapeEditing } from "$lib/utils/entityAnnotationEditing";
import { deleteEntity } from "$lib/utils/entityDeletion";
import { clearHighlighting } from "$lib/utils/highlightOperations";
import { acceptAnnotations, rejectAnnotations } from "$lib/utils/reviewActions";
import {
  clickBesideShapesKeepsFocus,
  clickEditsBoxes,
  followFocus,
  followReview,
  keepUnderReview,
  promptAnswerOfKey,
  reviewDecisionOfKey,
  reviewFirstAnnotation,
  reviewKeyIsFree,
  shapeHoldsWork,
  takeReviewKey,
  targetsToReview,
  type ReviewKeyContext,
  type ReviewKeyEvent,
  type ReviewTarget,
} from "$lib/utils/reviewKeyboard";
import { reviewStatusOf } from "$lib/utils/reviewStatus";
import { commitLoadedWorkspace } from "$lib/utils/workspaceRuntimeMutations";

// The review's keys, replayed on a record opened through the real loader and stores: one
// annotation at a time is under review, Enter accepts it, Delete rejects it, and the next one
// comes under review.

const DATASET_ID = "ds";
const RECORD_ID = "record-1";
const IMAGE_ID = "image-1";

const page = (items: unknown[]) => ({ items, total: items.length, limit: 1000, offset: 0 });
const jsonResponse = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200 });

/** The record's boxes: each names its entity, a model's and pending unless said. */
let boxes: { id: string; entity: string; source: "model" | "other"; status: string }[] = [];

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
    const rows = [...new Set(boxes.map((box) => box.entity))].map((id) => ({
      id,
      record_id: RECORD_ID,
      parent_id: "",
      created_at: "",
      updated_at: "",
    }));
    return Promise.resolve(jsonResponse(page(rows)));
  }
  if (path === "bboxes") {
    const rows = boxes.map(({ id, entity, source, status }) => ({
      id,
      record_id: RECORD_ID,
      view_id: IMAGE_ID,
      entity_id: entity,
      coords: [0.1, 0.1, 0.2, 0.2],
      format: "xywh",
      is_normalized: true,
      confidence: 0.8,
      source_type: source,
      source_name: source === "model" ? "detection" : "Pixano",
      source_metadata: "{}",
      review_status: status,
      created_at: "",
      updated_at: "",
    }));
    return Promise.resolve(jsonResponse(page(rows)));
  }
  return Promise.resolve(jsonResponse(page([])));
});

async function openRecord(): Promise<void> {
  const { workspaceData } = await loadWorkspaceRecord(DATASET_ID, RECORD_ID, WorkspaceType.IMAGE, [
    "bboxes",
  ]);
  commitLoadedWorkspace(workspaceData, { main: {}, objects: {} });
}

/** The entities as the inspector lists them: here, in id order. */
const listed = (): Entity[] => [...entities.value].sort((a, b) => a.id.localeCompare(b.id));

const shown = (id: string): Annotation => {
  const annotation = annotations.value.find((candidate) => candidate.id === id);
  if (!annotation) throw new Error(`The workspace does not show ${id}.`);
  return annotation;
};

const statusOf = (boxId: string) => {
  const box = annotations.value.find((annotation) => annotation.id === boxId);
  return box ? reviewStatusOf(box) : "deleted";
};

const staged = (): string[] =>
  saveData.value.map((mutation) => `${mutation.op} ${mutation.target.id}`).sort();

const key = (name: string, changes: Partial<ReviewKeyEvent> = {}): ReviewKeyEvent => ({
  key: name,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  shiftKey: false,
  repeat: false,
  defaultPrevented: false,
  ...changes,
});

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  // The focus scrolls the next entity's card into view: there is no page here.
  vi.stubGlobal("document", { querySelector: () => null });
  resetWorkspaceStores();
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetWorkspaceStores();
});

describe("the review's keys", () => {
  it.each([
    ["Enter", "accept"],
    ["Delete", "reject"],
    ["Backspace", "reject"],
  ])("%s asks to %s", (name, decision) => {
    expect(reviewDecisionOfKey(key(name))).toBe(decision);
  });

  it.each([
    ["another key", key("a")],
    ["a key with Ctrl", key("Enter", { ctrlKey: true })],
    ["a key with Cmd", key("Delete", { metaKey: true })],
    ["a key with Shift", key("Enter", { shiftKey: true })],
    ["a key held down", key("Enter", { repeat: true })],
    ["a key another handler took", key("Enter", { defaultPrevented: true })],
  ])("ask nothing for %s", (_, event) => {
    expect(reviewDecisionOfKey(event)).toBeNull();
  });
});

describe("the prompt to save and go to the next record", () => {
  it("goes with Enter", () => {
    expect(promptAnswerOfKey(key("Enter"))).toBe("go");
  });

  it.each([["Escape"], ["Delete"], ["a"]])("stays with %s", (name) => {
    expect(promptAnswerOfKey(key(name))).toBe("stay");
  });

  it.each([
    ["the Enter that opened it, held down", key("Enter", { repeat: true })],
    ["Shift alone", key("Shift", { shiftKey: true })],
    ["Cmd alone", key("Meta", { metaKey: true })],
  ])("hears no answer in %s", (_, event) => {
    expect(promptAnswerOfKey(event)).toBe("none");
  });
});

describe("when a key is free to decide", () => {
  const FREE: ReviewKeyContext = {
    toolType: ToolType.Pan,
    shape: { status: "none" },
    isEditing: false,
    isTyping: false,
    inOverlay: false,
    controlHasKeyboardFocus: false,
  };
  const selection: Shape = {
    status: "editing",
    shapeId: "box",
    viewRef: { id: IMAGE_ID, name: "image" },
    type: ShapeType.none,
  };

  it("with the Pan tool, nothing typed, no dialog and no shape in the works", () => {
    expect(reviewKeyIsFree("accept", FREE)).toBe(true);
  });

  it("after a click that only selected a shape", () => {
    // The canvas notes a selection as an edit of no type.
    expect(shapeHoldsWork(selection)).toBe(false);
    expect(reviewKeyIsFree("reject", { ...FREE, shape: selection })).toBe(true);
  });

  it.each([
    ["another tool", { toolType: ToolType.Rectangle }],
    ["text typed", { isTyping: true }],
    ["a dialog or a menu", { inOverlay: true }],
    ["a shape in edit mode, which Enter finishes", { isEditing: true }],
    ["a shape being drawn", { shape: { status: "creating" } as Shape }],
  ])("not with %s", (_, change) => {
    expect(reviewKeyIsFree("accept", { ...FREE, ...change })).toBe(false);
  });

  it("Enter not on a control a keyboard user reached, which it presses; Delete still", () => {
    const reached = { ...FREE, controlHasKeyboardFocus: true };

    expect(reviewKeyIsFree("accept", reached)).toBe(false);
    expect(reviewKeyIsFree("reject", reached)).toBe(true);
  });
});

describe("the annotations to review", () => {
  beforeEach(async () => {
    boxes = [
      { id: "a-1", entity: "a", source: "model", status: "accepted" },
      { id: "b-2", entity: "b", source: "model", status: "pending" },
      { id: "b-1", entity: "b", source: "model", status: "" },
      { id: "c-1", entity: "c", source: "other", status: "" },
      { id: "d-1", entity: "d", source: "model", status: "pending" },
    ];
    await openRecord();
  });

  it("go entity by entity, each entity's in the order of its card", () => {
    expect(targetsToReview(listed()).map(({ annotation }) => annotation.id)).toEqual([
      "b-1",
      "b-2",
      "d-1",
    ]);
  });

  it("leave whole an entity one of whose annotations to review is hidden", () => {
    const hidden = annotations.value.find((annotation) => annotation.id === "b-1");
    if (hidden) hidden.ui.displayControl = { ...hidden.ui.displayControl, hidden: true };

    expect(targetsToReview(listed()).map(({ annotation }) => annotation.id)).toEqual(["d-1"]);
  });

  it("start with the first, under review as a record opens in review", () => {
    expect(reviewFirstAnnotation(listed())).toBe(true);

    expect(reviewedAnnotation.value).toBe("b-1");
    expect(highlightedEntity.value).toBe("b");
  });

  it("start with the focused entity's, when the review is turned on with one focused", () => {
    highlightedEntity.value = "d";
    followFocus(listed(), "d");

    expect(reviewFirstAnnotation(listed())).toBe(true);

    expect(reviewedAnnotation.value).toBe("d-1");
    expect(highlightedEntity.value).toBe("d");
  });

  it("follow the focus: a click on another entity reviews its first", () => {
    followFocus(listed(), "d");
    expect(reviewedAnnotation.value).toBe("d-1");

    followFocus(listed(), "a");
    expect(reviewedAnnotation.value).toBeNull();
  });

  it("follow the focus from the entity's annotation in edit mode", () => {
    const edited = annotations.value.find((annotation) => annotation.id === "b-2");
    if (edited) edited.ui.displayControl = { ...edited.ui.displayControl, editing: true };

    followFocus(listed(), "b");

    expect(reviewedAnnotation.value).toBe("b-2");
  });

  it("keep the one under review while its entity stays focused", () => {
    reviewedAnnotation.value = "b-2";

    followFocus(listed(), "b");

    expect(reviewedAnnotation.value).toBe("b-2");
  });
});

describe("a key", () => {
  beforeEach(async () => {
    boxes = [
      { id: "a-box", entity: "a", source: "model", status: "pending" },
      { id: "a-mask", entity: "a", source: "model", status: "pending" },
      { id: "b-box", entity: "b", source: "model", status: "pending" },
      { id: "c-box", entity: "c", source: "other", status: "" },
    ];
    await openRecord();
    reviewFirstAnnotation(listed());
  });

  it("accepts the annotation under review alone, then reviews the entity's next", () => {
    expect(takeReviewKey("accept", listed(), highlightedEntity.value)).toBe("decided");

    expect(statusOf("a-box")).toBe(REVIEW_STATUS.ACCEPTED);
    expect(statusOf("a-mask")).toBe(REVIEW_STATUS.PENDING);
    expect(staged()).toEqual(["update a-box"]);
    expect(reviewedAnnotation.value).toBe("a-mask");
    expect(highlightedEntity.value).toBe("a");
  });

  it("rejects the annotation under review alone, then reviews the next", () => {
    expect(takeReviewKey("reject", listed(), highlightedEntity.value)).toBe("decided");

    expect(statusOf("a-box")).toBe("deleted");
    expect(statusOf("a-mask")).toBe(REVIEW_STATUS.PENDING);
    expect(staged()).toEqual(["delete a-box"]);
    expect(reviewedAnnotation.value).toBe("a-mask");
  });

  it("goes on to the next entity once one is done", () => {
    takeReviewKey("accept", listed(), highlightedEntity.value);
    takeReviewKey("reject", listed(), highlightedEntity.value);

    expect(reviewedAnnotation.value).toBe("b-box");
    expect(highlightedEntity.value).toBe("b");
  });

  it("decides nothing with none under review: it brings the focused entity's under review", () => {
    reviewedAnnotation.value = null;
    highlightedEntity.value = "b";

    expect(takeReviewKey("reject", listed(), highlightedEntity.value)).toBe("brought");

    expect(staged()).toEqual([]);
    expect(reviewedAnnotation.value).toBe("b-box");
  });

  it("decides nothing on an entity with nothing to review: it brings the next under review", () => {
    // A person's entity is looked at; Delete must not reach one out of sight.
    reviewedAnnotation.value = null;
    highlightedEntity.value = "c";

    expect(takeReviewKey("reject", listed(), highlightedEntity.value)).toBe("brought");

    expect(staged()).toEqual([]);
    expect(reviewedAnnotation.value).toBe("a-box");
  });

  it("wraps round to an annotation left to review before the one decided", () => {
    highlightedEntity.value = "b";
    followFocus(listed(), "b");

    takeReviewKey("accept", listed(), highlightedEntity.value);

    expect(reviewedAnnotation.value).toBe("a-box");
    expect(highlightedEntity.value).toBe("a");
  });

  it("puts none under review once the last is decided, and then does nothing", () => {
    takeReviewKey("accept", listed(), highlightedEntity.value);
    takeReviewKey("accept", listed(), highlightedEntity.value);
    takeReviewKey("accept", listed(), highlightedEntity.value);
    const decided = staged();

    expect(reviewedAnnotation.value).toBeNull();
    expect(highlightedEntity.value).toBeNull();
    expect(takeReviewKey("accept", listed(), highlightedEntity.value)).toBe("nothing");
    expect(staged()).toEqual(decided);
  });
});

describe("the annotation under review, as the annotations change", () => {
  let before: ReviewTarget[] = [];

  beforeEach(async () => {
    boxes = [
      { id: "a-box", entity: "a", source: "model", status: "pending" },
      { id: "a-mask", entity: "a", source: "model", status: "pending" },
      { id: "b-box", entity: "b", source: "model", status: "pending" },
      { id: "c-box", entity: "c", source: "other", status: "" },
    ];
    await openRecord();
    reviewFirstAnnotation(listed());
    before = targetsToReview(listed());
  });

  it("gives way to the next once accepted with the mouse", () => {
    acceptAnnotations([shown("a-box")]);

    keepUnderReview(before, listed());

    expect(reviewedAnnotation.value).toBe("a-mask");
    expect(highlightedEntity.value).toBe("a");
  });

  it("gives way to the next once rejected or deleted", () => {
    rejectAnnotations([shown("a-box")]);

    keepUnderReview(before, listed());

    expect(reviewedAnnotation.value).toBe("a-mask");
  });

  it("gives way to the next entity's once hidden: its entity waits whole", () => {
    const hidden = shown("a-box");
    hidden.ui.displayControl = { ...hidden.ui.displayControl, hidden: true };

    keepUnderReview(before, listed());

    expect(reviewedAnnotation.value).toBe("b-box");
    expect(highlightedEntity.value).toBe("b");
  });

  it("stays while it is still to review", () => {
    acceptAnnotations([shown("b-box")]);

    keepUnderReview(before, listed());

    expect(reviewedAnnotation.value).toBe("a-box");
  });

  it("leaves none under review, and no entity focused, once nothing is left", () => {
    acceptAnnotations(before.map(({ annotation }) => annotation));

    keepUnderReview(before, listed());

    expect(reviewedAnnotation.value).toBeNull();
    expect(highlightedEntity.value).toBeNull();
  });

  it("gives way to the focused entity's when it never was to review", () => {
    reviewedAnnotation.value = "c-box";
    highlightedEntity.value = "b";

    keepUnderReview(before, listed());

    expect(reviewedAnnotation.value).toBe("b-box");
  });

  it("stays with the focused entity under another tool, which focuses none", () => {
    selectedTool.value = rectangleTool;
    acceptAnnotations([shown("a-box")]);

    before = followReview(before, listed());
    expect(reviewedAnnotation.value).toBe("a-mask");

    acceptAnnotations([shown("a-mask")]);
    followReview(before, listed());

    expect(reviewedAnnotation.value).toBeNull();
    expect(highlightedEntity.value).toBe("a");
  });
});

describe("the review, as an entity's only annotation is deleted", () => {
  // The delete drops the focus on the entity it deletes: the review must move on before that lost
  // focus could end it.
  let before: ReviewTarget[] = [];

  beforeEach(async () => {
    boxes = [
      { id: "a-box", entity: "a", source: "model", status: "pending" },
      { id: "b-box", entity: "b", source: "model", status: "pending" },
      { id: "c-box", entity: "c", source: "model", status: "pending" },
    ];
    await openRecord();
    highlightedEntity.value = "b";
    followFocus(listed(), "b");
    before = targetsToReview(listed());
  });

  it("moves on after a Reject with the mouse", () => {
    rejectAnnotations([shown("b-box")]);
    expect(highlightedEntity.value).toBeNull();

    followReview(before, listed());

    expect(reviewedAnnotation.value).toBe("c-box");
    expect(highlightedEntity.value).toBe("c");
  });

  it("moves on after the box chip's delete, wrapping round past the last", () => {
    highlightedEntity.value = "c";
    followFocus(listed(), "c");
    before = targetsToReview(listed());
    const entity = entities.value.find((candidate) => candidate.id === "c");
    if (entity) deleteEntity(entity, shown("c-box"));
    clearHighlighting();

    followReview(before, listed());

    expect(reviewedAnnotation.value).toBe("a-box");
    expect(highlightedEntity.value).toBe("a");
  });
});

describe("a shape selected on the canvas", () => {
  beforeEach(async () => {
    boxes = [
      { id: "a-1", entity: "a", source: "model", status: "accepted" },
      { id: "b-1", entity: "b", source: "model", status: "pending" },
      { id: "b-2", entity: "b", source: "model", status: "pending" },
    ];
    await openRecord();
  });

  // What the canvas sends for a click that selects a shape without editing it.
  const select = (id: string) =>
    applyNewShapeEditing({
      status: "editing",
      shapeId: id,
      viewRef: { id: IMAGE_ID, name: "image" },
      highlighted: "self",
      type: ShapeType.none,
    });

  it("comes under review in review, its entity focused", () => {
    reviewModeIsActive.value = true;

    select("b-2");

    expect(reviewedAnnotation.value).toBe("b-2");
    expect(highlightedEntity.value).toBe("b");
  });

  it("does not under another tool, as Fusion, where a click picks something else", () => {
    reviewModeIsActive.value = true;
    selectedTool.value = fusionTool;

    select("b-2");

    expect(reviewedAnnotation.value).toBeNull();
  });

  it("does not out of review, nor when it is not to review", () => {
    select("b-2");
    expect(reviewedAnnotation.value).toBeNull();

    reviewModeIsActive.value = true;
    select("a-1");
    expect(reviewedAnnotation.value).toBeNull();
    expect(highlightedEntity.value).toBe("a");
  });
});

describe("a click on the canvas, in review", () => {
  it("selects a box without editing it, and keeps the review beside the shapes", () => {
    expect(clickEditsBoxes()).toBe(true);
    expect(clickBesideShapesKeepsFocus()).toBe(false);

    reviewModeIsActive.value = true;
    expect(clickEditsBoxes()).toBe(false);
    // With none under review, a click beside the shapes clears the focus as usual.
    expect(clickBesideShapesKeepsFocus()).toBe(false);

    reviewedAnnotation.value = "a-box";
    expect(clickBesideShapesKeepsFocus()).toBe(true);
  });
});
