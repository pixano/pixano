/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BBOX3D_RESOURCE, BBOX_RESOURCE, ENTITY_RESOURCE } from "$lib/api/resourceNames.js";

import type { CoordsNorm, ResourceMutation } from "./types.js";

const ID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

/**
 * Generate a short random id suitable for identifying a new entity or annotation
 * before the backend has assigned one. Matches the shape of pixano's nanoid(10).
 */
export function generateShortId(length = 10): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => ID_ALPHABET[b % ID_ALPHABET.length])
    .join("");
}

/**
 * Context required to build a BBox / Entity pair. Extracted from the widget's
 * options so the helper stays pure and easy to unit-test.
 */
export interface BuildContext {
  datasetId: string;
  recordId: string;
  viewId: string;
}

export interface BuildBBoxResult {
  entityId: string;
  bboxId: string;
  mutations: ResourceMutation[];
}

/**
 * Default annotation source metadata. Matches `PIXANO_SOURCE` in the legacy
 * pixano UI (`apps/pixano/src/lib/utils/entityLookupUtils.ts`) — using
 * `"other"` as the source type so we don't imply ground-truth provenance for
 * freshly drawn boxes.
 */
const DEFAULT_SOURCE = {
  source_type: "other",
  source_name: "Pixano",
  source_metadata: "{}",
} as const;

/**
 * Build the (entity, bbox) create mutation pair for a new 2D box annotation.
 *
 * The payloads match what the pixano backend `EntityCreate` / `BBoxCreate`
 * transport models expect (see `src/pixano/api/models.py`). In particular:
 *   - Entities only carry `{ id, record_id, parent_id }`. They do NOT carry
 *     source_* or timestamps: the `Entity` schema does not declare those
 *     fields and LanceModel-backed tables reject unknown ones.
 *   - BBoxes carry the full per-frame annotation shape including the
 *     required `source_*` and `view_id`/`frame_id` linkage fields.
 */
export function buildBBoxCreate(
  ctx: BuildContext,
  coordsNorm: CoordsNorm,
  opts: { widgetId?: string; localAnnotationId?: string; entityId?: string; bboxId?: string } = {},
): BuildBBoxResult {
  const entityId = opts.entityId ?? generateShortId();
  const bboxId = opts.bboxId ?? generateShortId();

  const entityBody: Record<string, unknown> = {
    id: entityId,
    record_id: ctx.recordId,
    parent_id: "",
  };

  const bboxBody: Record<string, unknown> = {
    id: bboxId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    // For single-image workspaces, the frame row and the view row are the
    // same id — mirrors what pixano's `defineCreatedAnnotation` does when
    // `isVideo === false`.
    frame_id: ctx.viewId,
    frame_index: -1,
    tracklet_id: "",
    entity_dynamic_state_id: "",
    coords: Array.from(coordsNorm),
    format: "xywh",
    is_normalized: true,
    confidence: 1,
    ...DEFAULT_SOURCE,
  };

  const mutations: ResourceMutation[] = [
    {
      op: "create",
      resource: ENTITY_RESOURCE,
      body: entityBody,
      widgetId: opts.widgetId,
      localAnnotationId: opts.localAnnotationId,
    },
    {
      op: "create",
      resource: BBOX_RESOURCE,
      body: bboxBody,
      widgetId: opts.widgetId,
      localAnnotationId: opts.localAnnotationId,
    },
  ];

  return { entityId, bboxId, mutations };
}

/**
 * Build an update body for an existing BBox whose geometry changed. Only
 * includes fields the backend's `BBoxUpdate` transport model accepts — the
 * server merges this onto the existing row.
 */
export function buildBBoxUpdate(
  ctx: BuildContext,
  bboxId: string,
  entityId: string,
  coordsNorm: CoordsNorm,
): Record<string, unknown> {
  return {
    id: bboxId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    coords: Array.from(coordsNorm),
    format: "xywh",
    is_normalized: true,
    confidence: 1,
    ...DEFAULT_SOURCE,
  };
}

/**
 * Build the (entity, bbox3d) create mutation pair for a new 3D box annotation.
 * Coordinates are in Lance/backend space (xyzwhd, Z-up). Rotation defaults to
 * identity — axis-aligned boxes only for now.
 */
export const DEFAULT_3D_ROTATION = [1, 0, 0, 0, 1, 0, 0, 0, 1];

export function buildBBox3DUpdate(
  ctx: BuildContext,
  bboxId: string,
  entityId: string,
  coordsLance: [number, number, number, number, number, number],
  rotation?: number[],
): Record<string, unknown> {
  return {
    id: bboxId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    coords: Array.from(coordsLance),
    format: "xyzwhd",
    rotation: rotation ?? DEFAULT_3D_ROTATION,
    is_normalized: false,
    confidence: 1,
    ...DEFAULT_SOURCE,
  };
}

export function buildBBox3DCreate(
  ctx: BuildContext,
  coordsLance: [number, number, number, number, number, number],
  opts: {
    widgetId?: string;
    localAnnotationId?: string;
    entityId?: string;
    bboxId?: string;
    rotation?: number[];
  } = {},
): BuildBBoxResult {
  const entityId = opts.entityId ?? generateShortId();
  const bboxId = opts.bboxId ?? generateShortId();

  const entityBody: Record<string, unknown> = {
    id: entityId,
    record_id: ctx.recordId,
    parent_id: "",
  };

  const bboxBody: Record<string, unknown> = {
    ...buildBBox3DUpdate(ctx, bboxId, entityId, coordsLance, opts.rotation),
    frame_id: ctx.viewId,
    frame_index: -1,
    tracklet_id: "",
    entity_dynamic_state_id: "",
  };

  const mutations: ResourceMutation[] = [
    {
      op: "create",
      resource: ENTITY_RESOURCE,
      body: entityBody,
      widgetId: opts.widgetId,
      localAnnotationId: opts.localAnnotationId,
    },
    {
      op: "create",
      resource: BBOX3D_RESOURCE,
      body: bboxBody,
      widgetId: opts.widgetId,
      localAnnotationId: opts.localAnnotationId,
    },
  ];

  return { entityId, bboxId, mutations };
}

/**
 * Flush ordering: an entity must be created before the annotations that
 * reference it, and deleted only after them — so creates run entity→annotation
 * and deletes run annotation→entity (entity delete last). Mirrors
 * `mutationPriority` in pixano's saveOrchestration.
 */
const MUTATION_PRIORITY = {
  entityCreate: 0,
  annotationCreate: 1,
  annotationDelete: 2,
  entityDelete: 3,
} as const;

export function mutationPriority(m: ResourceMutation): number {
  if (m.op === "delete") {
    return m.resource === ENTITY_RESOURCE
      ? MUTATION_PRIORITY.entityDelete
      : MUTATION_PRIORITY.annotationDelete;
  }
  return m.resource === ENTITY_RESOURCE
    ? MUTATION_PRIORITY.entityCreate
    : MUTATION_PRIORITY.annotationCreate;
}

export function sortMutations(mutations: ResourceMutation[]): ResourceMutation[] {
  return [...mutations].sort((a, b) => mutationPriority(a) - mutationPriority(b));
}
