/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get, writable, type Readable, type Writable } from "svelte/store";

import type { PreviewShape, ToolContext, ToolEvent, ToolFSM, ToolSideEffect, ToolState } from "@pixano/tools";

import type { ToolBridge } from "../types";
import type { CommandBridgeImpl } from "./CommandBridgeImpl";
import type { DocumentStoreImpl } from "./DocumentStoreImpl";

type RequestSaveCallback = (
  shapeType: "bbox" | "polygon" | "mask" | "keypoints",
  geometry: unknown,
) => void;

/**
 * Bridges tool FSMs to Svelte reactivity.
 *
 * Dispatches events to the active tool, processes state transitions,
 * and forwards side effects to the appropriate bridges.
 */
export class ToolBridgeImpl implements ToolBridge {
  readonly activeTool: Writable<ToolFSM>;
  private readonly _toolState: Writable<ToolState>;
  private readonly _preview: Writable<PreviewShape | null>;

  readonly toolState: Readable<ToolState>;
  readonly preview: Readable<PreviewShape | null>;

  private readonly commandBridge: CommandBridgeImpl;
  private readonly documentStore: DocumentStoreImpl;

  private canvasViewName = "";
  private canvasWidth = 0;
  private canvasHeight = 0;

  private requestSaveCallback: RequestSaveCallback | null = null;

  constructor(
    initialTool: ToolFSM,
    commandBridge: CommandBridgeImpl,
    documentStore: DocumentStoreImpl,
  ) {
    this.commandBridge = commandBridge;
    this.documentStore = documentStore;

    this.activeTool = writable(initialTool);
    this._toolState = writable(initialTool.getInitialState());
    this._preview = writable(null);

    this.toolState = { subscribe: this._toolState.subscribe };
    this.preview = { subscribe: this._preview.subscribe };
  }

  setCanvasContext(viewName: string, canvasWidth: number, canvasHeight: number): void {
    this.canvasViewName = viewName;
    this.canvasWidth = canvasWidth;
    this.canvasHeight = canvasHeight;
  }

  onRequestSave(callback: RequestSaveCallback): void {
    this.requestSaveCallback = callback;
  }

  dispatchEvent(event: ToolEvent): void {
    const tool = get(this.activeTool);
    const currentState = get(this._toolState);

    const context: ToolContext = {
      document: this.documentStore.getCurrentDocument(),
      selectedIds: get(this.documentStore.selectedIds),
      viewName: this.canvasViewName,
      canvasWidth: this.canvasWidth,
      canvasHeight: this.canvasHeight,
    };

    const { newState, sideEffects } = tool.transition(currentState, event, context);

    // Update state
    this._toolState.set(newState);

    // Process side effects
    for (const effect of sideEffects) {
      this.processSideEffect(effect);
    }
  }

  private processSideEffect(effect: ToolSideEffect): void {
    switch (effect.type) {
      case "emitCommand":
        this.commandBridge.execute(effect.command);
        break;
      case "updatePreview":
        this._preview.set(effect.preview);
        break;
      case "setCursor":
        // Cursor changes are handled by the canvas component via toolState
        break;
      case "beginTransaction":
        this.commandBridge.beginTransaction(effect.description);
        break;
      case "commitTransaction":
        this.commandBridge.commitTransaction();
        break;
      case "abortTransaction":
        this.commandBridge.abortTransaction();
        break;
      case "requestAI":
        // AI requests will be handled by the ComputeService in Phase 5
        console.warn("AI request side effect not yet implemented:", effect.requestId);
        break;
      case "cancelAI":
        console.warn("AI cancel side effect not yet implemented:", effect.requestId);
        break;
      case "requestSave":
        if (this.requestSaveCallback) {
          this.requestSaveCallback(effect.shapeType, effect.geometry);
        }
        break;
    }
  }

  /** Reset tool state when the active tool changes. */
  switchTool(tool: ToolFSM): void {
    this.activeTool.set(tool);
    this._toolState.set(tool.getInitialState());
    this._preview.set(null);
  }
}
