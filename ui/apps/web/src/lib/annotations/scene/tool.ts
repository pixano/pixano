/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";

import type Konva from "konva";

import type { Scene2DContext, Scene3DContext, SceneContextBase } from "./sceneContext.js";
import type { ToolDefinition } from "./toolDefinition.js";

export type { ToolDefinition } from "./toolDefinition.js";

/**
 * Default tool ids. They live here (a Konva-free module) so extensions and
 * tests can import them without dragging the tool implementations — and their
 * Konva dependency — into their bundle.
 */
export const DEFAULT_TOOL_2D = "select";
export const DEFAULT_TOOL_3D = "navigate";

/** Per-activation handler instance created by a 2D tool for one widget. */
export interface ToolHandler2D {
  activate?(): void;
  deactivate?(): void;
  onPointerDown?(event: Konva.KonvaEventObject<MouseEvent>): void;
  onPointerMove?(event: Konva.KonvaEventObject<MouseEvent>): void;
  onPointerUp?(event: Konva.KonvaEventObject<MouseEvent>): void;
  /** Return true when the event was consumed. */
  onKeyDown?(event: KeyboardEvent): boolean | void;
}

/** A 2D tool: toolbar metadata plus a handler factory. */
export interface Tool2D extends ToolDefinition {
  createHandler(ctx: Scene2DContext): ToolHandler2D;
}

/**
 * Generic state a 3D tool publishes back to the scene so the camera and the
 * renderers can react without knowing the tool's kind.
 */
export interface ToolHandle3D {
  /** True while the tool is capturing a pointer drag — the camera yields control. */
  readonly activeDragging: boolean;
  /** Committed annotation the tool is currently editing, or null — renderers skip it. */
  readonly editingId: string | null;
}

/**
 * Props the scene passes to a tool's overlay. The overlay publishes its
 * `ToolHandle3D` once via `reportHandle`, and the scene stores it by tool id (so
 * multiple editing tools never share one handle). Kind-specific host I/O (e.g. a
 * confirm callback) is forwarded opaquely by the scene, so it never appears here.
 */
export interface AnnotationTool3DProps {
  ctx: Scene3DContext;
  reportHandle?: (handle: ToolHandle3D) => void;
}

/**
 * Props for a tool's DOM HUD (rendered by the host widget *outside* the canvas,
 * e.g. a confirm panel). `session` is the tool's own editing session, opaque to
 * the host — the kind's HUD downcasts it. See `createSession` below.
 */
export interface ToolHudProps {
  session: unknown;
}

/**
 * A 3D tool: toolbar metadata plus, for editing tools, three kind-owned pieces
 * the host wires generically (the host names no kind):
 *  - `overlay`  — Threlte component: the interactive editor + transient preview.
 *  - `createSession` — builds the per-widget editing session (confirm state,
 *    gizmo visibility, commit), so kind-specific UI state never lives in the host.
 *  - `hud`      — DOM overlay (confirm/secondary UI) driven by that session.
 * Tools without scene interaction (e.g. navigate) omit all three.
 */
export interface Tool3D extends ToolDefinition {
  overlay?: Component<AnnotationTool3DProps>;
  hud?: Component<ToolHudProps>;
  createSession?: (seam: SceneContextBase) => unknown;
}
