/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PreviewShape, ToolContext, ToolEvent, ToolFSM, ToolSideEffect, ToolState } from "$lib/tools";
import type { AIRequestParams } from "$lib/types/tools";

import type { ReactiveReadonly, ReactiveValue, ToolBridge } from "$lib/types/store";
import type { ComputeJob } from "$lib/types/services";
import type { TrackerService } from "$lib/types/tracker";
import type { CommandBridgeImpl } from "./CommandBridgeImpl.svelte";
import type { DocumentStoreImpl } from "./DocumentStoreImpl.svelte";

type RequestSaveCallback = (
  shapeType: "bbox" | "polygon" | "mask" | "keypoints",
  geometry: unknown,
) => void;

type AIRequestCallback = (requestId: string, params: AIRequestParams) => void;

/**
 * Bridges tool FSMs to Svelte reactivity.
 *
 * Dispatches events to the active tool, processes state transitions,
 * and forwards side effects to the appropriate bridges.
 */
export class ToolBridgeImpl implements ToolBridge {
  private _activeTool = $state<ToolFSM>(undefined as unknown as ToolFSM);
  private _toolState = $state<ToolState>(undefined as unknown as ToolState);
  private _preview = $state<PreviewShape | null>(null);

  readonly activeTool: ReactiveValue<ToolFSM>;
  readonly toolState: ReactiveReadonly<ToolState>;
  readonly preview: ReactiveReadonly<PreviewShape | null>;

  private readonly commandBridge: CommandBridgeImpl;
  private readonly documentStore: DocumentStoreImpl;
  private trackerService: TrackerService | null = null;

  private canvasViewName = "";
  private canvasWidth = 0;
  private canvasHeight = 0;

  private requestSaveCallback: RequestSaveCallback | null = null;
  private aiRequestCallback: AIRequestCallback | null = null;
  private readonly activeAIJobs = new Map<string, ComputeJob>();

  constructor(
    initialTool: ToolFSM,
    commandBridge: CommandBridgeImpl,
    documentStore: DocumentStoreImpl,
  ) {
    this.commandBridge = commandBridge;
    this.documentStore = documentStore;

    this._activeTool = initialTool;
    this._toolState = initialTool.getInitialState();
    this._preview = null;

    const self = this;
    this.activeTool = {
      get value() { return self._activeTool; },
      set value(v: ToolFSM) { self._activeTool = v; },
      update(fn: (prev: ToolFSM) => ToolFSM) { self._activeTool = fn(self._activeTool); },
    };
    this.toolState = {
      get value() { return self._toolState; },
    };
    this.preview = {
      get value() { return self._preview; },
    };
  }

  setCanvasContext(viewName: string, canvasWidth: number, canvasHeight: number): void {
    this.canvasViewName = viewName;
    this.canvasWidth = canvasWidth;
    this.canvasHeight = canvasHeight;
  }

  onRequestSave(callback: RequestSaveCallback): void {
    this.requestSaveCallback = callback;
  }

  /** Register a callback for AI requests (allows custom handling). */
  onAIRequest(callback: AIRequestCallback): void {
    this.aiRequestCallback = callback;
  }

  /** Inject a TrackerService for handling AI tracking side effects. */
  setTrackerService(service: TrackerService): void {
    this.trackerService = service;
  }

  dispatchEvent(event: ToolEvent): void {
    const tool = this._activeTool;
    const currentState = this._toolState;

    const context: ToolContext = {
      document: this.documentStore.getCurrentDocument(),
      selectedIds: this.documentStore.selectedIds.value,
      viewName: this.canvasViewName,
      canvasWidth: this.canvasWidth,
      canvasHeight: this.canvasHeight,
    };

    const { newState, sideEffects } = tool.transition(currentState, event, context);

    // Update state
    this._toolState = newState;

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
        this._preview = effect.preview;
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
        if (this.aiRequestCallback) {
          this.aiRequestCallback(effect.requestId, effect.params);
        } else if (!this.trackerService) {
          console.warn("AI request received but no TrackerService or callback registered:", effect.requestId);
        }
        break;
      case "cancelAI": {
        const job = this.activeAIJobs.get(effect.requestId);
        if (job) {
          job.cancel();
          this.activeAIJobs.delete(effect.requestId);
        }
        break;
      }
      case "requestSave":
        if (this.requestSaveCallback) {
          this.requestSaveCallback(effect.shapeType, effect.geometry);
        }
        break;
    }
  }

  /** Reset tool state when the active tool changes. */
  switchTool(tool: ToolFSM): void {
    // Switching tools cancels any in-progress transactional drawing flow (e.g. polygon).
    try {
      this.commandBridge.abortTransaction();
    } catch {
      // No open transaction to abort.
    }
    this._activeTool = tool;
    this._toolState = tool.getInitialState();
    this._preview = null;
  }
}
