/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MutationGateway } from "./datasetGateway.js";
import type { WorkspaceSession } from "./workspaceSession.svelte.js";
import { sortMutations } from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import { ApiError } from "$lib/api/apiClient.js";
import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";

/**
 * Lookup the queue uses to mark a local annotation as persisted after a
 * successful create. Annotations live on the record's shared collection,
 * so the lookup needs only the local annotation id.
 *
 * Returning `undefined` is fine — it just means the record was switched
 * mid-flush and the persistence flag doesn't need flipping.
 */
export interface LocalAnnotationLocator {
  findLocalAnnotation(localAnnotationId: string): { persisted: boolean } | undefined;
}

/**
 * Owns the queue of pending mutations and the flush lifecycle.
 *
 * Depends on `MutationGateway` only, so adding new read endpoints to the
 * data layer can never widen this class's surface.
 *
 * A mutation leaves `pending` as its request leaves, and is `inFlight` until
 * the backend answers. Nothing queued later can reach it: an edit made on a row
 * whose request is on the wire is queued after it, never written into a body
 * the server has already been sent — which would drop it unsent once that
 * request returned.
 */
export class MutationQueue {
  pending = $state<ResourceMutation[]>([]);
  /** The mutation whose request is on the wire, if any. */
  inFlight = $state<ResourceMutation | null>(null);
  saving = $state(false);
  saveError = $state<string | null>(null);

  /** Every change not yet stored, the one on the wire included. */
  count = $derived(this.pending.length + (this.inFlight ? 1 : 0));

  /**
   * Bumped by `reset`, so that a request still in flight when the queue was
   * abandoned — another record opened — neither comes back into the new
   * record's queue on failure nor reports its error there.
   */
  private generation = 0;

  constructor(
    private gateway: MutationGateway,
    private session: WorkspaceSession,
    private locator: LocalAnnotationLocator,
  ) {}

  /** Append a mutation to the queue. Order matters; `flush` re-orders only
   * by resource (entities first, then annotations, deletes last) via
   * `sortMutations` — within a resource the original order is preserved. */
  queue(mutation: ResourceMutation): void {
    this.append(mutation);
  }

  /**
   * Queue an update, or — if an update for the same resource+id is already
   * pending — replace its body. Lets an annotation be edited repeatedly before
   * a save without piling up redundant updates for the same row. Owning this
   * here keeps the "find-pending-update-or-queue" logic out of renderers and
   * widgets (it was duplicated in both).
   *
   * The latest queued update is the one replaced: after a failed request, the
   * row may hold that one and a newer one queued while it was on the wire, and
   * they are sent in order. The gesture that wrote the body owns the work, so
   * its `widgetId` comes with it.
   */
  upsertUpdate(mutation: Extract<ResourceMutation, { op: "update" }>): void {
    const existing = this.pending.findLast(
      (m) => m.op === "update" && m.resource === mutation.resource && m.id === mutation.id,
    );
    if (existing && existing.op === "update") {
      existing.body = mutation.body;
      existing.widgetId = mutation.widgetId;
    } else {
      this.append(mutation);
    }
  }

  /**
   * Merge `patch` into the body of a still-pending *create* for the given local
   * annotation, if one exists (no-op otherwise). Lets a freshly drawn,
   * not-yet-saved annotation be re-edited so its queued create carries the
   * latest geometry. Owning this here keeps callers from reaching into
   * `pending` and mutating a queued mutation's body in place.
   *
   * A create already on the wire is not patched — the server has its body. The
   * row exists once it lands, so the patch follows it as an update of that row
   * (the local annotation id doubles as the row id). Should that create fail,
   * it comes back to the head of the queue with that update behind it, and a
   * later patch goes into the update: written into the create, it would be
   * overwritten by the older body the update sends after it.
   */
  patchPendingCreate(
    localAnnotationId: string,
    resource: string,
    patch: Record<string, unknown>,
  ): void {
    const pending = this.pending.find(
      (m) =>
        m.op === "create" && m.resource === resource && m.localAnnotationId === localAnnotationId,
    );
    const queuedUpdate = this.pending.findLast(
      (m) => m.op === "update" && m.resource === resource && m.id === localAnnotationId,
    );
    if (pending && pending.op === "create" && !queuedUpdate) {
      Object.assign(pending.body, patch);
      return;
    }
    // On the wire, or back in the queue with an update of its row behind it.
    const create = pending ?? this.inFlight;
    if (
      create?.op !== "create" ||
      create.resource !== resource ||
      create.localAnnotationId !== localAnnotationId
    ) {
      return;
    }
    this.upsertUpdate({
      op: "update",
      resource,
      id: localAnnotationId,
      body: { ...(queuedUpdate?.op === "update" ? queuedUpdate.body : {}), ...patch },
      widgetId: create.widgetId,
      localAnnotationId,
    });
  }

  /**
   * Drop every queued mutation that references the given local annotation id.
   * Used when an annotation is deleted locally before it has been persisted,
   * so we don't POST-then-DELETE it for nothing.
   */
  /**
   * Forget an entity this annotation was going to be moved onto, because the
   * user then picked a different one.
   *
   * Changing your mind twice before saving used to leave the first entity
   * behind: `upsertUpdate` replaces the annotation's update so only the last
   * choice is referenced, but the creates piled up, and the abandoned one was
   * written to the dataset with nothing pointing at it. Correcting a mistake
   * should not litter.
   */
  dropPendingEntityCreate(localAnnotationId: string): void {
    this.pending = this.pending.filter(
      (m) =>
        !(
          m.op === "create" &&
          m.resource === ENTITY_RESOURCE &&
          m.localAnnotationId === localAnnotationId
        ),
    );
  }

  dropForLocalAnnotation(localAnnotationId: string): ResourceMutation[] {
    const dropped: ResourceMutation[] = [];
    this.pending = this.pending.filter((m) => {
      if (m.localAnnotationId === localAnnotationId) {
        dropped.push(m);
        return false;
      }
      return true;
    });
    return dropped;
  }

  /** Reset the queue without flushing. Used when clearing the workspace. */
  reset(): void {
    this.pending = [];
    this.saveError = null;
    this.generation++;
  }

  /**
   * Flush every queued mutation to the backend. Entities are created
   * before the annotations that reference them; deletes run last. On success,
   * the corresponding local annotation (if any) is marked `persisted: true`
   * via the locator the manager provided.
   */
  async flush(): Promise<void> {
    if (this.saving) return;
    const datasetId = this.session.datasetId;
    if (!datasetId) {
      this.saveError = "No dataset selected.";
      return;
    }
    if (this.pending.length === 0) {
      // Whatever failed is no longer queued — a draft whose create failed and
      // was then deleted — so there is no failure left to report.
      this.saveError = null;
      return;
    }

    this.saving = true;
    this.saveError = null;
    const generation = this.generation;

    // Snapshot and sort; elements are still the same object references as in
    // this.pending, so each leaves it by identity as its request leaves.
    const toProcess = sortMutations([...this.pending]);

    try {
      for (const mutation of toProcess) {
        await this.send(datasetId, mutation, generation);
      }
    } catch (err) {
      if (generation === this.generation) this.saveError = describeFailure(err);
    } finally {
      this.saving = false;
    }
  }

  /** Append to the queue; returns the mutation as the queue holds it. */
  private append(mutation: ResourceMutation): ResourceMutation {
    this.pending.push(mutation);
    // Read back rather than returned as given: the queue holds its own
    // reactive copy, the object `flush` sends and identifies by reference.
    return this.pending[this.pending.length - 1];
  }

  /**
   * Send one mutation. It leaves `pending` as its request leaves, so nothing
   * queued meanwhile can be written into it, and comes back at the head of the
   * queue if the request fails — unless the queue was reset meanwhile: then
   * there is nothing to retry.
   */
  private async send(
    datasetId: string,
    mutation: ResourceMutation,
    generation: number,
  ): Promise<void> {
    this.pending = this.pending.filter((m) => m !== mutation);
    this.inFlight = mutation;
    try {
      await this.run(datasetId, mutation);
    } catch (err) {
      this.inFlight = null;
      this.failed(mutation, err, generation);
      return;
    }
    this.inFlight = null;
    this.landed(mutation);
  }

  /** What a write that landed leaves to do. */
  private landed(mutation: ResourceMutation): void {
    if (
      mutation.op === "create" &&
      mutation.resource !== ENTITY_RESOURCE &&
      mutation.localAnnotationId
    ) {
      const annotation = this.locator.findLocalAnnotation(mutation.localAnnotationId);
      if (annotation) annotation.persisted = true;
    }
  }

  /**
   * What a write that failed leaves to do; throws its error. It comes back at
   * the head of the queue, unless the queue was reset meanwhile.
   */
  private failed(mutation: ResourceMutation, err: unknown, generation: number): void {
    if (generation === this.generation) this.pending = [mutation, ...this.pending];
    throw err;
  }

  private async run(datasetId: string, mutation: ResourceMutation): Promise<void> {
    if (mutation.resource === ENTITY_RESOURCE) {
      if (mutation.op === "create") {
        await this.gateway.createEntity(datasetId, mutation.body);
      } else if (mutation.op === "delete") {
        await this.gateway.deleteEntity(datasetId, mutation.id);
      }
      return;
    }
    if (mutation.op === "create") {
      await this.gateway.createAnnotation(datasetId, mutation.resource, mutation.body);
    } else if (mutation.op === "update") {
      await this.gateway.updateAnnotation(datasetId, mutation.resource, mutation.id, mutation.body);
    } else if (mutation.op === "delete") {
      await this.gateway.deleteAnnotation(datasetId, mutation.resource, mutation.id);
    }
  }
}

/**
 * The message a failed save shows. An `ApiError` carries the backend's
 * `detail`, so the user can see why the request was rejected (e.g. "Invalid
 * data: <field> extra inputs are not permitted" or "Foreign key violation:
 * record_id=…").
 */
function describeFailure(err: unknown): string {
  if (err instanceof ApiError) return `${err.message}: ${err.body}`;
  return err instanceof Error ? err.message : String(err);
}
