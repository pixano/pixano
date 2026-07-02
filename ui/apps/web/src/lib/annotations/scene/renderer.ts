/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";

import type { AnnotationKind } from "../annotationCollection.svelte.js";

import type { Scene2DContext, Scene2DReadContext, Scene3DContext } from "./sceneContext.js";

/**
 * Displays one annotation kind on the 2D scene: pure display plus selection.
 * It receives a read-only context, so it physically cannot write to the queue —
 * editing input lives in an `AnnotationEditor2D` (docs/ARCHITECTURE_TOOLING.md,
 * decision D4). One instance per widget; lives in the kind's folder under `kinds/`.
 */
export interface AnnotationRenderer2D {
  readonly kind: AnnotationKind;
  /** Reconcile scene nodes with the collection. */
  sync(): void;
  destroy(): void;
}

/**
 * Handles editing input for one kind on the 2D scene (drag / transform → commit)
 * and owns its interaction widgets (e.g. a `Konva.Transformer`). It gets the full
 * `Scene2DContext` (it may write to the queue, unlike a renderer). The widget
 * calls `syncSelection()` whenever the rendered nodes or selection change.
 */
export interface AnnotationEditor2D {
  readonly kind: AnnotationKind;
  syncSelection(): void;
  destroy(): void;
}

/** Registry entry: builds the display renderer, and optionally an input editor. */
export interface AnnotationRenderer2DFactory {
  readonly kind: AnnotationKind;
  create(ctx: Scene2DReadContext): AnnotationRenderer2D;
  /** Optional input handler; absent for display-only kinds. */
  createEditor?(ctx: Scene2DContext): AnnotationEditor2D;
}

/**
 * Props every 3D renderer component receives. A 3D renderer is a Svelte
 * component (not an imperative object) because Threlte rendering *is* declarative
 * markup; it pulls its kind from `ctx.collection.byKind(...)` and emits the
 * Threlte nodes for it, exactly like the 2D renderer's `sync()` but reactive.
 */
export interface AnnotationRenderer3DProps {
  ctx: Scene3DContext;
}

/** Registry entry: the component that renders one kind inside the 3D scene. */
export interface AnnotationRenderer3DFactory {
  readonly kind: AnnotationKind;
  readonly component: Component<AnnotationRenderer3DProps>;
}
