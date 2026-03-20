/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  AIRequestParams,
  InteractivePromptMode,
  LabeledClick,
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolSideEffect,
  ToolState,
  ToolTransition,
} from "$lib/types/tools";

type BoxDraft = {
  origin: { x: number; y: number };
  current: { x: number; y: number };
};

type PromptBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export class InteractiveSegmenterToolFSM implements ToolFSM {
  readonly id = "interactive-segmenter";
  readonly name = "Interactive segmenter";
  readonly icon = "magic-wand";
  readonly defaultCursor = "crosshair";

  private promptMode: InteractivePromptMode;
  private points: LabeledClick[] = [];
  private box: PromptBox | null = null;

  constructor(promptMode: InteractivePromptMode = "positive") {
    this.promptMode = promptMode;
  }

  getInitialState(): ToolState {
    this.points = [];
    this.box = null;
    return { phase: "idle" };
  }

  transition(state: ToolState, event: ToolEvent, context: ToolContext): ToolTransition {
    if (event.type === "setInteractivePromptMode") {
      this.promptMode = event.promptMode;
      return this.withPreview(state);
    }

    if (event.type === "keyDown" && (event.key === "x" || event.key === "X")) {
      this.promptMode = this.promptMode === "negative" ? "positive" : "negative";
      return this.withPreview(state);
    }

    if (event.type === "keyDown" && (event.key === "r" || event.key === "R")) {
      this.promptMode = "box";
      return this.withPreview(state);
    }

    if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
      if (this.points.length === 0 && this.box === null) {
        return {
          newState: { phase: "idle" },
          sideEffects: [{ type: "updatePreview", preview: null }],
        };
      }

      this.points = [];
      this.box = null;
      return {
        newState: { phase: "idle" },
        sideEffects: [
          { type: "updatePreview", preview: null },
          this.requestAI(context, "clear"),
        ],
      };
    }

    if (event.type === "confirm" || (event.type === "keyDown" && event.key === "Enter")) {
      if (this.points.length === 0 && this.box === null) {
        return { newState: state, sideEffects: [] };
      }

      return {
        newState: { phase: "collectingPoints", points: this.points },
        sideEffects: [this.requestAI(context, "confirm")],
      };
    }

    switch (state.phase) {
      case "idle":
      case "collectingPoints":
        if (this.promptMode === "box") {
          return this.handleBoxMode(state, event, context);
        }
        return this.handlePointMode(state, event, context);

      case "drawing":
        return this.handleBoxMode(state, event, context);

      default:
        return { newState: state, sideEffects: [] };
    }
  }

  private handlePointMode(
    state: ToolState,
    event: ToolEvent,
    context: ToolContext,
  ): ToolTransition {
    if (event.type !== "pointerDown" || event.button !== 0) {
      return { newState: state, sideEffects: [] };
    }

    const label = this.promptMode === "negative" ? 0 : 1;
    this.points = [...this.points, { ...event.position, label }];

    return {
      newState: { phase: "collectingPoints", points: this.points },
      sideEffects: [
        this.previewEffect(),
        this.requestAI(context, "predict"),
      ],
    };
  }

  private handleBoxMode(state: ToolState, event: ToolEvent, context: ToolContext): ToolTransition {
    if (state.phase !== "drawing" && event.type === "pointerDown" && event.button === 0) {
      return {
        newState: { phase: "drawing", origin: event.position, current: event.position },
        sideEffects: [this.previewEffect({ origin: event.position, current: event.position })],
      };
    }

    if (state.phase === "drawing" && event.type === "pointerMove") {
      return {
        newState: { phase: "drawing", origin: state.origin, current: event.position },
        sideEffects: [this.previewEffect({ origin: state.origin, current: event.position })],
      };
    }

    if (state.phase === "drawing" && event.type === "pointerUp") {
      const width = event.position.x - state.origin.x;
      const height = event.position.y - state.origin.y;
      if (Math.abs(width) <= 2 || Math.abs(height) <= 2) {
        return {
          newState: this.points.length > 0 ? { phase: "collectingPoints", points: this.points } : { phase: "idle" },
          sideEffects: [this.previewEffect()],
        };
      }

      this.box = {
        x: Math.min(state.origin.x, event.position.x),
        y: Math.min(state.origin.y, event.position.y),
        width: Math.abs(width),
        height: Math.abs(height),
      };

      return {
        newState: { phase: "collectingPoints", points: this.points },
        sideEffects: [this.previewEffect(), this.requestAI(context, "predict")],
      };
    }

    return { newState: state, sideEffects: [] };
  }

  private withPreview(state: ToolState): ToolTransition {
    return {
      newState: state,
      sideEffects: [this.previewEffect(state.phase === "drawing" ? state : null)],
    };
  }

  private previewEffect(draftBox: BoxDraft | null = null): ToolSideEffect {
    return {
      type: "updatePreview",
      preview: {
        type: "interactive-segmenter",
        promptMode: this.promptMode,
        points: this.points,
        box: this.box,
        draftBox,
      },
    };
  }

  private requestAI(
    context: ToolContext,
    action: "predict" | "confirm" | "clear",
  ): ToolSideEffect {
    const requestId = `interactive-segmenter-${Date.now()}`;
    const params: AIRequestParams = {
      modelId: "interactive-segmenter",
      input: {
        type: "interactive-segmenter",
        action,
        viewRef: {
          id: context.viewId,
          name: context.viewName,
        },
        promptMode: this.promptMode,
        prompt: {
          points: this.points,
          box: this.box,
        },
      },
    };

    return {
      type: "requestAI",
      requestId,
      params,
    };
  }
}
