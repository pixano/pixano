/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { toRawAnnotation } from "$lib/api/adapters";
import type { RecordComponentResponse } from "$lib/api/restTypes";
import { ToolType } from "$lib/tools";
import { Annotation, Entity, WorkspaceType } from "$lib/types/dataset";
import {
  annotationShownAlone,
  getEffectiveHighlight,
  isHiddenByReview,
} from "$lib/utils/highlightUtils";

// How a shape stands out on the canvas: "self" in full view, "none" faded, "all" as usual.

const MODEL = { source_type: "model", source_name: "detection", source_metadata: "{}" };
const PERSON = { source_type: "other", source_name: "Pixano", source_metadata: "{}" };

function box(id: string, entityId: string, row: Record<string, unknown>): Annotation {
  const component = {
    id,
    record_id: "record-1",
    view_id: "view-1",
    entity_id: entityId,
    coords: [0.1, 0.1, 0.2, 0.2],
    format: "xywh",
    is_normalized: true,
    confidence: 0.8,
    created_at: "",
    updated_at: "",
    ...row,
  } as RecordComponentResponse;
  const raw = toRawAnnotation(component, new Map([["view-1", "image"]]), "bboxes");
  const annotation = Annotation.deepCreateInstanceArray({ bboxes: [raw] }).bboxes[0];
  annotation.ui.datasetItemType = WorkspaceType.IMAGE;
  return annotation;
}

const pending = box("pending", "dog", { ...MODEL, review_status: "pending" });
const accepted = box("accepted", "cat", { ...MODEL, review_status: "accepted" });
const drawn = box("drawn", "bird", PERSON);

const entitiesById = new Map(
  ["dog", "cat", "bird"].map((id) => [id, { id, data: { parent_id: "" } } as unknown as Entity]),
);

const highlight = (
  annotation: Annotation,
  reviewing: boolean,
  focused: string | null = null,
  tool: ToolType = ToolType.Pan,
) => getEffectiveHighlight(annotation, focused, tool, focused ? entitiesById : null, reviewing);

describe("in review", () => {
  it("what is still to review stays in view, and what exists already fades", () => {
    // Not "self": the canvas reads it as a shape selected already, which a click cannot select.
    expect(highlight(pending, true)).toBe("all");
    expect(highlight(accepted, true)).toBe("none");
    expect(highlight(drawn, true)).toBe("none");
  });

  it("an Accept not saved yet fades the annotation at once", () => {
    const justAccepted = box("just-accepted", "dog", { ...MODEL, review_status: "pending" });
    justAccepted.ui.unsavedAccept = true;

    expect(highlight(justAccepted, true)).toBe("none");
  });

  it("a shape being edited stays in full view", () => {
    const edited = box("edited", "cat", { ...MODEL, review_status: "accepted" });
    edited.ui.displayControl = { ...edited.ui.displayControl, editing: true };

    expect(highlight(edited, true)).toBe("all");
  });

  it("a focused object stands out most; the rest to review stays in view", () => {
    expect(highlight(accepted, true, "cat")).toBe("self");
    expect(highlight(pending, true, "cat")).toBe("all");
    expect(highlight(drawn, true, "cat")).toBe("none");
  });

  it("follows the review whatever the tool, a focus counting with the Pan tool only", () => {
    expect(highlight(pending, true, null, ToolType.Rectangle)).toBe("all");
    expect(highlight(pending, true, "cat", ToolType.Rectangle)).toBe("all");
    expect(highlight(accepted, true, "cat", ToolType.Rectangle)).toBe("none");
  });

  it("leaves a highlight a tool set, as the object Fusion picked", () => {
    const picked = box("picked", "cat", { ...MODEL, review_status: "accepted" });
    picked.ui.displayControl = { ...picked.ui.displayControl, highlighted: "self" };

    expect(highlight(picked, true, null, ToolType.Fusion)).toBe("self");
  });
});

describe("out of review", () => {
  it("each shape shows as its own display says", () => {
    expect(highlight(pending, false)).toBe("all");
    expect(highlight(accepted, false)).toBe("all");
  });

  it("a focused object stands out in the Pan tool", () => {
    expect(highlight(pending, false, "dog")).toBe("self");
    expect(highlight(drawn, false, "dog")).toBe("none");
  });
});

describe("with an annotation under review", () => {
  it("only it is drawn, with a shape being edited", () => {
    const edited = box("edited", "cat", { ...MODEL, review_status: "accepted" });
    edited.ui.displayControl = { ...edited.ui.displayControl, editing: true };

    expect(isHiddenByReview(pending, "pending")).toBe(false);
    expect(isHiddenByReview(accepted, "pending")).toBe(true);
    expect(isHiddenByReview(drawn, "pending")).toBe(true);
    expect(isHiddenByReview(edited, "pending")).toBe(false);
  });

  it("nothing is hidden with none under review", () => {
    expect(isHiddenByReview(accepted, null)).toBe(false);
  });

  it("it is shown alone in review, with the Pan tool, while it is shown", () => {
    const shownAlone = (id: string, reviewing = true, tool: ToolType = ToolType.Pan) =>
      annotationShownAlone([pending, accepted, drawn], id, reviewing, tool);

    expect(shownAlone("pending")).toBe("pending");
    expect(shownAlone("pending", false)).toBeNull();
    // A drawing tool shows the record whole, so that a shape is not drawn twice.
    expect(shownAlone("pending", true, ToolType.Rectangle)).toBeNull();
    // Deleted, it hides nothing until the next one comes under review.
    expect(shownAlone("deleted")).toBeNull();
  });

  it("nothing is hidden while it is hidden itself", () => {
    const hidden = box("hidden", "dog", { ...MODEL, review_status: "pending" });
    hidden.ui.displayControl = { ...hidden.ui.displayControl, hidden: true };

    expect(annotationShownAlone([hidden], "hidden", true, ToolType.Pan)).toBeNull();
  });
});
