/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { KeypointsGeometry } from "./keypointsTypes.js";
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
export const KEYPOINTS_RESOURCE = "keypoints";

/**
 * Update body for a skeleton. Matches the backend `KeyPointsUpdate` transport
 * model, built from `KeyPoints` — which has **no `confidence` column** (like
 * CompressedRLE, unlike BBox), so sending one would be rejected.
 *
 * INVARIANT (D9): `buildCreate`'s body must be a superset of this one with
 * identical values outside the geometry, so `commitGeometryEdit` can patch a
 * still-pending create with it.
 */
export function buildKeypointsUpdate(
  ctx: BuildContext,
  keypointsId: string,
  entityId: string,
  geometry: KeypointsGeometry,
): Record<string, unknown> {
  return {
    id: keypointsId,
    record_id: ctx.recordId,
    entity_id: entityId,
    view_id: ctx.viewId,
    template_id: geometry.templateId,
    coords: [...geometry.coords],
    states: [...geometry.states],
    ...DEFAULT_SOURCE,
  };
}

/** The (entity, keypoints) create mutation pair for a newly placed skeleton. */
export function buildKeypointsCreate(
  ctx: BuildContext,
  geometry: KeypointsGeometry,
  opts: BuildAnnotationOpts = {},
): BuildAnnotationResult {
  const entityId = opts.entityId ?? generateShortId();
  const annotationId = opts.annotationId ?? generateShortId();

  const body: Record<string, unknown> = {
    ...buildKeypointsUpdate(ctx, annotationId, entityId, geometry),
    ...singleFrameLinkage(ctx),
  };

  return {
    entityId,
    annotationId,
    mutations: buildCreateMutations(
      ctx,
      KEYPOINTS_RESOURCE,
      { entityId, annotationId },
      body,
      opts,
    ),
  };
}

/**
 * Payload knowledge for keypoint skeletons. The local annotation id doubles as
 * the backend row id, as for every other kind.
 */
export const keypointsPayloadBuilder = {
  kind: "keypoints" as const,
  resource: KEYPOINTS_RESOURCE,

  buildCreate(
    ctx: BuildContext,
    annotation: LocalAnnotation<KeypointsGeometry>,
    widgetId: string,
    entity: EntityCreateChoice = {},
  ): ResourceMutation[] {
    return buildKeypointsCreate(ctx, annotation.geometry, {
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
    annotation: LocalAnnotation<KeypointsGeometry>,
  ): Record<string, unknown> {
    return buildKeypointsUpdate(ctx, annotation.id, annotation.entityId, annotation.geometry);
  },
};
