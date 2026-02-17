/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";
import { describe, expect, it } from "vitest";

import { CommandProcessorImpl, createAddAnnotation } from "@pixano/commands";
import type { NodeId } from "@pixano/document";
import {
  createBBoxAnnotationNode,
  createEmptyDocument,
} from "@pixano/document/test/helpers";
import { RectangleToolFSM } from "@pixano/tools";

import { CommandBridgeImpl } from "../../src/impl/CommandBridgeImpl";
import { DocumentStoreImpl } from "../../src/impl/DocumentStoreImpl";
import { ToolBridgeImpl } from "../../src/impl/ToolBridgeImpl";

/**
 * Integration test: Full rectangle flow without UI.
 *
 * Chain: ToolBridge → RectangleToolFSM → requestSave callback →
 *        CommandBridge.execute(AddAnnotation) → DocumentStore updated →
 *        undo removes annotation → redo restores it.
 */
describe("Rectangle tool flow (integration)", () => {
  function setup() {
    const doc = createEmptyDocument();
    const documentStore = new DocumentStoreImpl(doc);
    const processor = new CommandProcessorImpl();
    const commandBridge = new CommandBridgeImpl(processor, documentStore);
    const tool = new RectangleToolFSM();
    const toolBridge = new ToolBridgeImpl(tool, commandBridge, documentStore);

    toolBridge.setCanvasContext("image", 800, 600);

    return { toolBridge, commandBridge, documentStore, processor };
  }

  it("should complete draw → editingNew → confirm → save flow", () => {
    const { toolBridge, commandBridge, documentStore } = setup();

    // Wire up requestSave to create an annotation via CommandBridge
    toolBridge.onRequestSave((shapeType, geometry) => {
      expect(shapeType).toBe("bbox");
      const geo = geometry as { x: number; y: number; width: number; height: number };

      // Create a normalized annotation from the raw geometry
      const ann = createBBoxAnnotationNode({
        id: "ann-flow-1" as NodeId,
        data: {
          coords: [geo.x / 800, geo.y / 600, geo.width / 800, geo.height / 600],
          format: "xywh",
          is_normalized: true,
          confidence: -1,
        },
      });
      commandBridge.execute(createAddAnnotation(ann));
    });

    // 1. Pointer down — start drawing
    toolBridge.dispatchEvent({
      type: "pointerDown",
      position: { x: 100, y: 50 },
      button: 0,
    });
    expect(get(toolBridge.toolState).phase).toBe("drawing");

    // 2. Pointer move — update preview
    toolBridge.dispatchEvent({
      type: "pointerMove",
      position: { x: 300, y: 250 },
    });
    expect(get(toolBridge.toolState).phase).toBe("drawing");
    expect(get(toolBridge.preview)).not.toBeNull();

    // 3. Pointer up — transition to editingNew
    toolBridge.dispatchEvent({
      type: "pointerUp",
      position: { x: 300, y: 250 },
    });
    expect(get(toolBridge.toolState).phase).toBe("editingNew");
    const preview = get(toolBridge.preview);
    expect(preview?.type).toBe("rectangle");
    if (preview?.type === "rectangle") {
      expect(preview.editable).toBe(true);
    }

    // 4. Confirm — triggers requestSave → callback creates annotation
    toolBridge.dispatchEvent({ type: "confirm" });
    expect(get(toolBridge.toolState).phase).toBe("idle");
    expect(get(toolBridge.preview)).toBeNull();

    // Verify annotation was created in the document
    const annotations = get(documentStore.annotations);
    expect(annotations).toHaveLength(1);
    expect(annotations[0].id).toBe("ann-flow-1");

    // 5. Undo — annotation removed
    commandBridge.undo();
    expect(get(documentStore.annotations)).toHaveLength(0);

    // 6. Redo — annotation restored
    commandBridge.redo();
    const restoredAnnotations = get(documentStore.annotations);
    expect(restoredAnnotations).toHaveLength(1);
    expect(restoredAnnotations[0].id).toBe("ann-flow-1");
  });

  it("should cancel drawing without creating annotation", () => {
    const { toolBridge, documentStore } = setup();

    let saveCalled = false;
    toolBridge.onRequestSave(() => {
      saveCalled = true;
    });

    // Draw
    toolBridge.dispatchEvent({
      type: "pointerDown",
      position: { x: 100, y: 50 },
      button: 0,
    });
    toolBridge.dispatchEvent({
      type: "pointerUp",
      position: { x: 300, y: 250 },
    });
    expect(get(toolBridge.toolState).phase).toBe("editingNew");

    // Cancel instead of confirm
    toolBridge.dispatchEvent({ type: "cancel" });
    expect(get(toolBridge.toolState).phase).toBe("idle");
    expect(get(toolBridge.preview)).toBeNull();
    expect(saveCalled).toBe(false);
    expect(get(documentStore.annotations)).toHaveLength(0);
  });

  it("should discard zero-area click without entering editingNew", () => {
    const { toolBridge } = setup();

    let saveCalled = false;
    toolBridge.onRequestSave(() => {
      saveCalled = true;
    });

    // Click (no movement)
    toolBridge.dispatchEvent({
      type: "pointerDown",
      position: { x: 100, y: 50 },
      button: 0,
    });
    toolBridge.dispatchEvent({
      type: "pointerUp",
      position: { x: 100, y: 50 },
    });

    expect(get(toolBridge.toolState).phase).toBe("idle");
    expect(saveCalled).toBe(false);
  });

  it("should cancel during drawing phase via Escape", () => {
    const { toolBridge } = setup();

    toolBridge.dispatchEvent({
      type: "pointerDown",
      position: { x: 100, y: 50 },
      button: 0,
    });
    expect(get(toolBridge.toolState).phase).toBe("drawing");

    toolBridge.dispatchEvent({ type: "keyDown", key: "Escape" });
    expect(get(toolBridge.toolState).phase).toBe("idle");
    expect(get(toolBridge.preview)).toBeNull();
  });
});
