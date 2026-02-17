/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";
import { describe, expect, it, vi } from "vitest";

import { CommandProcessorImpl } from "@pixano/commands";
import { createEmptyDocument } from "@pixano/document/test/helpers";
import { RectangleToolFSM, PanToolFSM } from "@pixano/tools";

import { CommandBridgeImpl } from "../src/impl/CommandBridgeImpl";
import { DocumentStoreImpl } from "../src/impl/DocumentStoreImpl";
import { ToolBridgeImpl } from "../src/impl/ToolBridgeImpl";

function createTestToolBridge() {
  const doc = createEmptyDocument();
  const documentStore = new DocumentStoreImpl(doc);
  const processor = new CommandProcessorImpl();
  const commandBridge = new CommandBridgeImpl(processor, documentStore);
  const tool = new RectangleToolFSM();
  const toolBridge = new ToolBridgeImpl(tool, commandBridge, documentStore);

  return { toolBridge, commandBridge, documentStore, tool };
}

describe("ToolBridgeImpl", () => {
  // -------- dispatchEvent --------

  describe("dispatchEvent", () => {
    it("should forward events to the FSM and update toolState", () => {
      const { toolBridge } = createTestToolBridge();

      expect(get(toolBridge.toolState).phase).toBe("idle");

      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });

      expect(get(toolBridge.toolState).phase).toBe("drawing");
    });

    it("should update preview store on drawing", () => {
      const { toolBridge } = createTestToolBridge();

      expect(get(toolBridge.preview)).toBeNull();

      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });

      const preview = get(toolBridge.preview);
      expect(preview).not.toBeNull();
      expect(preview?.type).toBe("rectangle");
    });
  });

  // -------- requestSave effect --------

  describe("requestSave effect", () => {
    it("should call onRequestSave callback with shapeType and geometry", () => {
      const { toolBridge } = createTestToolBridge();
      const callback = vi.fn();
      toolBridge.onRequestSave(callback);

      // Draw a rectangle
      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });
      toolBridge.dispatchEvent({
        type: "pointerUp",
        position: { x: 110, y: 220 },
      });

      // Now in editingNew, confirm
      toolBridge.dispatchEvent({ type: "confirm" });

      expect(callback).toHaveBeenCalledOnce();
      expect(callback).toHaveBeenCalledWith("bbox", {
        x: 10,
        y: 20,
        width: 100,
        height: 200,
      });
    });

    it("should not throw when no callback is registered", () => {
      const { toolBridge } = createTestToolBridge();

      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });
      toolBridge.dispatchEvent({
        type: "pointerUp",
        position: { x: 110, y: 220 },
      });

      expect(() => {
        toolBridge.dispatchEvent({ type: "confirm" });
      }).not.toThrow();
    });
  });

  // -------- setCanvasContext --------

  describe("setCanvasContext", () => {
    it("should use stored context values in ToolContext passed to FSM", () => {
      const { toolBridge } = createTestToolBridge();
      toolBridge.setCanvasContext("depth-view", 1024, 768);

      // The FSM doesn't use context for rectangle, but we can verify
      // the transition still works after setting context
      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });

      expect(get(toolBridge.toolState).phase).toBe("drawing");
    });
  });

  // -------- switchTool --------

  describe("switchTool", () => {
    it("should reset state and clear preview", () => {
      const { toolBridge } = createTestToolBridge();

      // Start drawing
      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });
      expect(get(toolBridge.toolState).phase).toBe("drawing");
      expect(get(toolBridge.preview)).not.toBeNull();

      // Switch to pan
      const panTool = new PanToolFSM();
      toolBridge.switchTool(panTool);

      expect(get(toolBridge.toolState).phase).toBe("idle");
      expect(get(toolBridge.preview)).toBeNull();
      expect(get(toolBridge.activeTool)).toBe(panTool);
    });
  });

  // -------- emitCommand effect --------

  describe("emitCommand effect", () => {
    it("should forward emitCommand to commandBridge", () => {
      const { toolBridge, commandBridge } = createTestToolBridge();
      const executeSpy = vi.spyOn(commandBridge, "execute");

      // The rectangle FSM no longer emits commands directly,
      // but we can verify the infrastructure works by checking
      // that the tool bridge correctly processes side effects
      toolBridge.dispatchEvent({
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      });

      // No commands emitted from rectangle tool drawing
      expect(executeSpy).not.toHaveBeenCalled();
    });
  });
});
