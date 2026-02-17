/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import type { ToolEvent, Point2D } from "@pixano/tools";

/**
 * Translates Konva stage events into framework-agnostic ToolEvent objects.
 *
 * Usage: attach to a Konva.Stage instance and provide a dispatch callback.
 * The adapter handles coordinate transformation from screen to canvas space.
 */
export class KonvaEventAdapter {
  private readonly stage: Konva.Stage;
  private readonly dispatch: (event: ToolEvent) => void;
  private cleanupFns: Array<() => void> = [];

  constructor(stage: Konva.Stage, dispatch: (event: ToolEvent) => void) {
    this.stage = stage;
    this.dispatch = dispatch;
  }

  /** Attach event listeners to the stage. */
  attach(): void {
    const onMouseDown = (e: Konva.KonvaEventObject<MouseEvent>) => {
      const pos = this.getPointerPosition();
      if (!pos) return;
      this.dispatch({
        type: "pointerDown",
        position: pos,
        button: e.evt.button,
      });
    };

    const onMouseMove = () => {
      const pos = this.getPointerPosition();
      if (!pos) return;
      this.dispatch({
        type: "pointerMove",
        position: pos,
      });
    };

    const onMouseUp = () => {
      const pos = this.getPointerPosition();
      if (!pos) return;
      this.dispatch({
        type: "pointerUp",
        position: pos,
      });
    };

    const onKeyDown = (e: KeyboardEvent) => {
      this.dispatch({
        type: "keyDown",
        key: e.key,
        modifiers: {
          shift: e.shiftKey,
          ctrl: e.ctrlKey,
          alt: e.altKey,
          meta: e.metaKey,
        },
      });
    };

    const onKeyUp = (e: KeyboardEvent) => {
      this.dispatch({
        type: "keyUp",
        key: e.key,
      });
    };

    this.stage.on("mousedown", onMouseDown);
    this.stage.on("mousemove", onMouseMove);
    this.stage.on("mouseup", onMouseUp);

    // Keyboard events on the document (stage doesn't receive keyboard events)
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keyup", onKeyUp);

    this.cleanupFns = [
      () => this.stage.off("mousedown", onMouseDown),
      () => this.stage.off("mousemove", onMouseMove),
      () => this.stage.off("mouseup", onMouseUp),
      () => document.removeEventListener("keydown", onKeyDown),
      () => document.removeEventListener("keyup", onKeyUp),
    ];
  }

  /** Remove all event listeners. */
  detach(): void {
    for (const cleanup of this.cleanupFns) {
      cleanup();
    }
    this.cleanupFns = [];
  }

  /** Get the pointer position in canvas coordinates (accounting for stage transforms). */
  private getPointerPosition(): Point2D | null {
    const pos = this.stage.getPointerPosition();
    if (!pos) return null;
    return { x: pos.x, y: pos.y };
  }
}
