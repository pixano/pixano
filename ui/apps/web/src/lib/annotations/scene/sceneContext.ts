/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import type { PerspectiveCamera } from "three";
import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type {
  AnnotationKind,
  AnnotationStore,
  GeometryByKind,
} from "../annotationCollection.svelte.js";
import type { BuildContext } from "../buildPayloads.js";
import type { CameraCalibration, PendingAnnotation, ResourceMutation } from "../types.js";

/**
 * Transient in-progress geometry an editing tool broadcasts on every pointer
 * move, so widgets in other mediums can preview the gesture live (e.g. an image
 * widget re-projecting a 3D box while it is dragged). Deliberately NOT an
 * `AnnotationStore` entry: the store contract covers committed annotations
 * (membership, selection, deletion), while this is per-frame editor state that
 * dies with the gesture. A distributed union so `draft.kind` narrows `geometry`.
 */
export type LiveAnnotationDraft = {
  [K in AnnotationKind]: LiveDraftBody<K> & {
    /** Widget owning the gesture, stamped by the seam — never by the publisher. */
    readonly sourceWidgetId: string;
  };
}[AnnotationKind];

/**
 * The part of a draft a publisher supplies. `sourceWidgetId` is deliberately
 * absent: the seam stamps it, so a tool can neither forge another widget's id
 * nor forget to set its own.
 */
type LiveDraftBody<K extends AnnotationKind> = {
  readonly kind: K;
  readonly geometry: GeometryByKind[K];
  /** Persisted annotation being edited, or null when creating a new one. */
  readonly editingId: string | null;
};

/** What a tool hands to `LiveDraftChannel.publish`. */
export type LiveDraftPublication = {
  [K in AnnotationKind]: LiveDraftBody<K>;
}[AnnotationKind];

/** Read side of the live-draft slot — all a renderer, or any 2D tool, may hold (D4). */
export interface LiveDraftSource {
  get(): LiveAnnotationDraft | null;
}

/**
 * Write side, handed only to the pieces that own a gesture (see `SeamContext`).
 * Ownership is structural rather than by convention: `publish` stamps the
 * caller's widget id, and `clear` is a no-op unless the live draft belongs to
 * that same widget — so no tool can wipe a gesture running in another widget,
 * whether or not its author remembered the rule.
 */
export interface LiveDraftChannel extends LiveDraftSource {
  publish(draft: LiveDraftPublication): void;
  clear(): void;
}

/**
 * Narrow view of the mutation queue handed to tools and renderers: enough to
 * queue work and reconcile pending creates, nothing more. Medium-agnostic, so
 * 2D and 3D scenes share it.
 */
export interface MutationSink {
  readonly pending: readonly ResourceMutation[];
  queue(mutation: ResourceMutation): void;
  /** Queue an update, or replace the body of a pending update for the same resource+id. */
  upsertUpdate(mutation: Extract<ResourceMutation, { op: "update" }>): void;
  /** Merge a patch into a still-pending create's body for the given local annotation. */
  patchPendingCreate(
    localAnnotationId: string,
    resource: string,
    patch: Record<string, unknown>,
  ): void;
  dropForLocalAnnotation(localAnnotationId: string): void;
  /**
   * Drop a still-pending *entity* create queued for this annotation, if any.
   *
   * Narrower than `dropForLocalAnnotation` on purpose: that one also discards a
   * pending geometry update, which a reassignment has no business undoing.
   */
  dropPendingEntityCreate(localAnnotationId: string): void;
}

/**
 * The medium-agnostic core every scene context shares. The widget builds this
 * "seam" (a view-scoped collection plus a mutation sink); per-medium contexts
 * (`Scene2DContext`, `Scene3DContext`) extend it with their engine handles.
 *
 * Tools and renderers depend on this interface (or a medium subtype), never on
 * the widget or the `WorkspaceManager` directly — that's the dependency
 * inversion the plugin system rests on.
 */
export interface SceneContextBase {
  readonly widgetId: string;
  readonly buildContext: BuildContext;
  /** View-scoped window onto the record's shared annotation collection. */
  readonly collection: AnnotationStore;
  readonly mutations: MutationSink;
  /**
   * Shared slot for the in-progress geometry of the active editing gesture.
   * Read-only here: observing a gesture is medium-agnostic, but *publishing* one
   * is a capability handed explicitly through `SeamContext`.
   */
  readonly liveDraft: LiveDraftSource;
  /** Switch the widget's active tool (e.g. back to "select" after a draw). */
  setActiveTool(id: string): void;
  /** Ask the host to re-sync annotation rendering. */
  requestRedraw(): void;
  /**
   * Register a freshly drawn annotation awaiting its entity choice: the host
   * surfaces the Inspector's entity form, then calls back to commit or discard.
   */
  beginPendingAnnotation(pending: PendingAnnotation): void;
  /** Resolve an existing entity row, for the label snapshot on entity assignment. */
  findEntity(entityId: string): Record<string, unknown> | undefined;
  /** Whether an entity's persisted annotations should currently be shown. */
  isEntityVisible(entityId: string): boolean;
}

/**
 * What `buildSeam` returns: `SceneContextBase` plus the live-draft *write* side.
 * Handed only to the pieces that own a gesture — today a 3D tool's session, via
 * `Tool3D.createSession`. Every narrower contract (`Scene2DContext`,
 * `Scene3DContext`) sees `liveDraft` as a read-only `LiveDraftSource`, so
 * publishing is a capability granted deliberately rather than one every tool in
 * every medium inherits. Same technique as `Scene2DReadContext`: one object,
 * handed out through progressively narrower types (D4).
 */
export interface SeamContext extends SceneContextBase {
  readonly liveDraft: LiveDraftChannel;
}

/**
 * The image's media dimensions and camera calibration, for kinds that project
 * into the 2D scene (e.g. rendering a bbox3d as a projected wireframe).
 */
export interface Scene2DCamera {
  readonly imageWidth: number;
  readonly imageHeight: number;
  readonly calibration: CameraCalibration | null;
}

/**
 * The read-only slice of the 2D scene a **renderer** may touch: it can display
 * annotations and manage selection, but has no `mutations` and no
 * `setActiveTool`, so a renderer cannot write to the queue or switch tools. This
 * makes "renderers display, tools/editors handle input" (D4) true by
 * construction. The full `Scene2DContext` extends it (adds the write surface).
 */
export interface Scene2DReadContext {
  readonly widgetId: string;
  readonly buildContext: BuildContext;
  readonly collection: AnnotationStore;
  readonly stage: Konva.Stage;
  readonly annotationLayer: Konva.Layer;
  /** Media size + calibration, for kinds that project into the image. */
  readonly camera: Scene2DCamera;
  /** Read-only view of the shared live-draft slot, for live previews. */
  readonly liveDraft: LiveDraftSource;
  getKonvaImage(): Konva.Image | null;
  requestRedraw(): void;
  /** Whether an entity's persisted annotations should currently be shown. */
  isEntityVisible(entityId: string): boolean;
}

/**
 * Everything a 2D (Konva) tool handler or **editor** may touch — the read slice
 * (`Scene2DReadContext`) plus the write surface (`mutations`, `setActiveTool`
 * from `SceneContextBase`). The widget finishes building it once its Konva stage
 * exists, then hands the same instance to every tool and editor in that widget.
 */
export interface Scene2DContext extends SceneContextBase, Scene2DReadContext {}

/**
 * Everything a 3D (Threlte) renderer or tool may touch. The widget builds the
 * agnostic seam (`SceneContextBase`); the Threlte scene *finishes* this context
 * because the camera and controls only exist once the `<Canvas>` has mounted.
 */
export interface Scene3DContext extends SceneContextBase {
  /**
   * Id of the annotation currently captured by the active editing tool, if
   * any. Static renderers skip it so the tool's live preview is the only copy
   * on screen. Null when nothing is being edited.
   */
  readonly editingId: string | null;
  /** Default camera; `.current` is the live PerspectiveCamera. */
  readonly camera: { current: PerspectiveCamera };
  /** OrbitControls instance, or null before the scene has mounted them. */
  getControls(): ThreeOrbitControls | null;
  /** World Y of the ground plane (scene's lowest point), for ground raycasts. */
  readonly floorY: number;
  /** Orbit pivot in world space — a sensible spawn point for new annotations. */
  readonly cameraTarget: [number, number, number];
  /** Camera-to-pivot distance, used to scale default annotation sizes. */
  readonly orbitCenterDist: number;
  /** Active tool id, so a tool overlay can tell when it is the selected tool. */
  readonly activeToolId: string;
}
