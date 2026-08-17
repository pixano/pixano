/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ResourceMutation } from "./types.js";
import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";

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
 * Context required to build an annotation / Entity pair. Extracted from the
 * widget's options so the helper stays pure and easy to unit-test.
 */
export interface BuildContext {
  datasetId: string;
  recordId: string;
  viewId: string;
}

/** What a kind's create builder returns: the ids it minted and its mutations. */
export interface BuildAnnotationResult {
  entityId: string;
  annotationId: string;
  mutations: ResourceMutation[];
}

/**
 * Options shared by every kind's create builder.
 *
 *  - `entityFields` are merged into the new entity's body (e.g. `{ category }`).
 *  - `linkExisting` attaches the annotation to an entity that already exists:
 *    the entity-create mutation is omitted and `entityId` must be supplied.
 */
export interface BuildAnnotationOpts {
  widgetId?: string;
  localAnnotationId?: string;
  entityId?: string;
  annotationId?: string;
  entityFields?: Record<string, unknown>;
  linkExisting?: boolean;
}

/**
 * The entity decision threaded from the Inspector form to a kind's create
 * builder: merge `entityFields` into a new entity, or `linkExisting` to attach
 * the box to an already-existing entity (the annotation's `entityId`) and skip
 * the entity-create. Empty `{}` means "new anonymous entity".
 */
export interface EntityCreateChoice {
  entityFields?: Record<string, unknown>;
  linkExisting?: boolean;
}

/**
 * Default annotation source metadata. Matches `PIXANO_SOURCE` in the legacy
 * pixano UI (`apps/pixano/src/lib/utils/entityLookupUtils.ts`) — using
 * `"other"` as the source type so we don't imply ground-truth provenance for
 * freshly drawn boxes.
 */
export const DEFAULT_SOURCE = {
  source_type: "other",
  source_name: "Pixano",
  source_metadata: "{}",
} as const;

/**
 * The linkage columns every per-frame annotation carries. For single-image
 * workspaces the frame row and the view row are the same id — mirrors what
 * pixano's `defineCreatedAnnotation` does when `isVideo === false`. Video would
 * make these real (see D2, out of scope).
 */
export function singleFrameLinkage(ctx: BuildContext): Record<string, unknown> {
  return {
    frame_id: ctx.viewId,
    frame_index: -1,
    tracklet_id: "",
    entity_dynamic_state_id: "",
  };
}

/**
 * The create mutation for a new entity. Entities carry only
 * `{ id, record_id, parent_id }` plus any user-supplied fields (the `Entity`
 * schema rejects unknown columns). Shared by every kind's create builder and by
 * the entity-reassignment flow, so the entity body lives in exactly one place.
 */
export function buildEntityCreateMutation(
  ctx: BuildContext,
  entityId: string,
  entityFields: Record<string, unknown> | undefined,
  widgetId: string | undefined,
  localAnnotationId: string | undefined,
): ResourceMutation {
  return {
    op: "create",
    resource: ENTITY_RESOURCE,
    body: { id: entityId, record_id: ctx.recordId, parent_id: "", ...entityFields },
    widgetId,
    localAnnotationId,
  };
}

/**
 * Assemble a kind's create mutations: the entity-create (unless the annotation
 * links an entity that already exists) followed by the annotation row itself.
 * Every kind's `buildCreate` funnels through here, so the entity/annotation
 * ordering and the widget/local-id bookkeeping live in exactly one place — a
 * new kind supplies only its `resource` and body.
 */
export function buildCreateMutations(
  ctx: BuildContext,
  resource: string,
  ids: { entityId: string; annotationId: string },
  body: Record<string, unknown>,
  opts: BuildAnnotationOpts,
): ResourceMutation[] {
  return [
    // `linkExisting` attaches the annotation to an entity that already exists,
    // so the entity-create is skipped (the chosen entityId is supplied in opts).
    ...(opts.linkExisting
      ? []
      : [
          buildEntityCreateMutation(
            ctx,
            ids.entityId,
            opts.entityFields,
            opts.widgetId,
            opts.localAnnotationId,
          ),
        ]),
    {
      op: "create",
      resource,
      body,
      widgetId: opts.widgetId,
      localAnnotationId: opts.localAnnotationId,
    },
  ];
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
