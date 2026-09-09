/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MultiPathGeometry } from "./multiPathTypes.js";
import type { LocalAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
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
import type { ResourceMutation } from "$lib/annotations/types.js";

/** Backend table this kind writes to. Owned here — nothing else declares it. */
export const MULTI_PATH_RESOURCE = "multi-paths";

/**
 * Update body for a multi-path. Matches the backend `MultiPathUpdate` transport
 * model; like CompressedRLE and KeyPoints it has **no `confidence` column**.
 *
 * This is also the one place that renames the geometry's camelCase fields to
 * the snake_case columns — nothing else needs to know `num_points`/`is_closed`.
 *
 * INVARIANT (D9): `buildCreate`'s body must be a superset of this one with
 * identical values outside the geometry, so `commitGeometryEdit` can patch a
 * still-pending create with it.
 */
export function buildMultiPathUpdate(
  ctx: BuildContext,
  multiPathId: string,
  entityId: string,
  geometry: MultiPathGeometry,
): Record<string, unknown> {
  return {
    id: multiPathId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    coords: [...geometry.coords],
    num_points: [...geometry.numPoints],
    is_closed: geometry.isClosed,
    ...DEFAULT_SOURCE,
  };
}

/** The (entity, multi-path) create mutation pair for a newly drawn path. */
export function buildMultiPathCreate(
  ctx: BuildContext,
  geometry: MultiPathGeometry,
  opts: BuildAnnotationOpts = {},
): BuildAnnotationResult {
  const entityId = opts.entityId ?? generateShortId();
  const annotationId = opts.annotationId ?? generateShortId();

  const body: Record<string, unknown> = {
    ...buildMultiPathUpdate(ctx, annotationId, entityId, geometry),
    ...singleFrameLinkage(ctx),
  };

  return {
    entityId,
    annotationId,
    mutations: buildCreateMutations(
      ctx,
      MULTI_PATH_RESOURCE,
      { entityId, annotationId },
      body,
      opts,
    ),
  };
}

/**
 * Payload knowledge for multi-paths. One builder serves both polygons and
 * polylines — they differ only by the `is_closed` flag the geometry carries,
 * which is why they are one kind with two tools rather than two kinds.
 */
export const multiPathPayloadBuilder = {
  kind: "multi_path" as const,
  resource: MULTI_PATH_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<MultiPathGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildMultiPathCreate(ctx, annotation.geometry, {
      widgetId,
      localAnnotationId: annotation.id,
      entityId: annotation.entityId,
      annotationId: annotation.id,
      entityFields: entity.entityFields,
      linkExisting: entity.linkExisting,
    }).mutations;
  },

  buildUpdate(
    ctx: BuildContext,
    annotation: LocalAnnotation<MultiPathGeometry>,
  ): Record<string, unknown> {
    return buildMultiPathUpdate(ctx, annotation.id, annotation.entityId, annotation.geometry);
  },
};
