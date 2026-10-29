/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  BBox3DGeometry,
  LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import {
  buildCreateMutations,
  DEFAULT_SOURCE,
  generateShortId,
  singleFrameLinkage,
  type BuildAnnotationOpts,
  type BuildAnnotationResult,
  type BuildContext,
  type EntityCreateChoice,
} from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation, Rotation3x3 } from "$lib/annotations/types.js";

/** Backend table this kind writes to. Owned here — nothing else declares it. */
export const BBOX3D_RESOURCE = "bbox3ds";

/** Identity rotation: an axis-aligned box carries no orientation. */
export const DEFAULT_3D_ROTATION: Rotation3x3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

/** Lance/backend coordinates: centre + size, Z-up. */
type CoordsLance = [number, number, number, number, number, number];

/**
 * Update body for a 3D box. Coordinates are in Lance/backend space, in
 * `format` — xyzwhd, what the editor writes, unless the box is stored as
 * corners; rotation is a row-major 3×3 matrix, identity when the box is
 * axis-aligned.
 *
 * INVARIANT (D9): `buildCreate`'s body must be a superset of this one with
 * identical values outside the geometry, so `commitGeometryEdit` can patch a
 * still-pending create with it.
 */
export function buildBBox3DUpdate(
  ctx: BuildContext,
  bboxId: string,
  entityId: string,
  coordsLance: CoordsLance,
  rotation?: Rotation3x3,
  format: BBox3DGeometry["format"] = "xyzwhd",
): Record<string, unknown> {
  return {
    id: bboxId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    coords: Array.from(coordsLance),
    format,
    rotation: rotation ?? DEFAULT_3D_ROTATION,
    is_normalized: false,
    confidence: 1,
    ...DEFAULT_SOURCE,
  };
}

/** The (entity, bbox3d) create mutation pair for a new 3D box. */
export function buildBBox3DCreate(
  ctx: BuildContext,
  coordsLance: CoordsLance,
  opts: BuildAnnotationOpts & {
    rotation?: Rotation3x3;
    format?: BBox3DGeometry["format"];
  } = {},
): BuildAnnotationResult {
  const entityId = opts.entityId ?? generateShortId();
  const annotationId = opts.annotationId ?? generateShortId();

  const body: Record<string, unknown> = {
    ...buildBBox3DUpdate(ctx, annotationId, entityId, coordsLance, opts.rotation, opts.format),
    ...singleFrameLinkage(ctx),
  };

  return {
    entityId,
    annotationId,
    mutations: buildCreateMutations(ctx, BBOX3D_RESOURCE, { entityId, annotationId }, body, opts),
  };
}

/**
 * Payload knowledge for 3D boxes. The local annotation id doubles as the
 * backend row id (see bboxPayloadBuilder); editor output is always xyzwhd.
 */
export const bbox3dPayloadBuilder = {
  kind: "bbox3d" as const,
  resource: BBOX3D_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<BBox3DGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildBBox3DCreate(ctx, annotation.geometry.coords, {
      widgetId,
      localAnnotationId: annotation.id,
      entityId: annotation.entityId,
      annotationId: annotation.id,
      rotation: annotation.geometry.rotation,
      format: annotation.geometry.format,
      entityFields: entity.entityFields,
      linkExisting: entity.linkExisting,
    }).mutations;
  },

  /**
   * The box as it stands, under the view and in the format it is stored with.
   * A 3D box belongs to the record, not to a sensor: any 3D widget of the
   * record edits it, so the editing widget's view is not the box's — and a box
   * imported as corners stays in corners until the editor moves it. Written
   * from the widget instead, an edit that changed nothing else would still
   * change the row. A box drawn here carries the view of the widget that drew
   * it, the one its create was built with.
   */
  buildUpdate(
    ctx: BuildContext,
    annotation: LocalAnnotation<BBox3DGeometry>,
  ): Record<string, unknown> {
    return buildBBox3DUpdate(
      { ...ctx, viewId: annotation.viewId },
      annotation.id,
      annotation.entityId,
      annotation.geometry.coords,
      annotation.geometry.rotation,
      annotation.geometry.format,
    );
  },
};
