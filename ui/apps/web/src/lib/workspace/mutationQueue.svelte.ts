/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { sortMutations } from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import { ApiError } from "$lib/api/apiClient.js";
import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";

import type { MutationGateway } from "./datasetGateway.js";
import type { WorkspaceSession } from "./workspaceSession.svelte.js";

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
 */
export class MutationQueue {
  pending = $state<ResourceMutation[]>([]);
  saving = $state(false);
  saveError = $state<string | null>(null);

  count = $derived(this.pending.length);

  constructor(
    private gateway: MutationGateway,
    private session: WorkspaceSession,
    private locator: LocalAnnotationLocator,
  ) {}

  /** Append a mutation to the queue. Order matters; `flush` re-orders only
   * by resource (entities first, then bboxes, deletes last) via
   * `sortMutations` — within a resource the original order is preserved. */
  queue(mutation: ResourceMutation): void {
    this.pending.push(mutation);
  }

  /**
   * Queue an update, or — if an update for the same resource+id is already
   * pending — replace its body. Lets an annotation be edited repeatedly before
   * a save without piling up redundant updates for the same row. Owning this
   * here keeps the "find-pending-update-or-queue" logic out of renderers and
   * widgets (it was duplicated in both).
   */
  upsertUpdate(mutation: Extract<ResourceMutation, { op: "update" }>): void {
    const existing = this.pending.find(
      (m) => m.op === "update" && m.resource === mutation.resource && m.id === mutation.id,
    );
    if (existing && existing.op === "update") existing.body = mutation.body;
    else this.pending.push(mutation);
  }

  /**
   * Merge `patch` into the body of a still-pending *create* for the given local
   * annotation, if one exists (no-op otherwise). Lets a freshly drawn,
   * not-yet-saved annotation be re-edited so its queued create carries the
   * latest geometry. Owning this here keeps callers from reaching into
   * `pending` and mutating a queued mutation's body in place.
   */
  patchPendingCreate(
    localAnnotationId: string,
    resource: string,
    patch: Record<string, unknown>,
  ): void {
    const pending = this.pending.find(
      (m) => m.op === "create" && m.resource === resource && m.localAnnotationId === localAnnotationId,
    );
    if (pending && pending.op === "create") Object.assign(pending.body, patch);
  }

  /**
   * Drop every queued mutation that references the given local bbox id.
   * Used when a bbox is deleted locally before it has been persisted, so
   * we don't POST-then-DELETE it for nothing.
   */
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
    if (this.pending.length === 0) return;

    this.saving = true;
    this.saveError = null;

    // Snapshot and sort; elements are still the same object references as in
    // this.pending so we can filter by identity after each successful run.
    const toProcess = sortMutations([...this.pending]);

    try {
      for (const mutation of toProcess) {
        await this.run(datasetId, mutation);
        // Drop the just-applied mutation immediately so a mid-flush failure
        // does not re-send already-persisted mutations on the next flush.
        this.pending = this.pending.filter((m) => m !== mutation);
        if (
          mutation.op === "create" &&
          mutation.resource !== ENTITY_RESOURCE &&
          mutation.localAnnotationId
        ) {
          const annotation = this.locator.findLocalAnnotation(mutation.localAnnotationId);
          if (annotation) annotation.persisted = true;
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        // Surface the backend's `detail` so the user can see why the
        // request was rejected (e.g. "Invalid data: <field> extra inputs
        // are not permitted" or "Foreign key violation: record_id=…").
        this.saveError = `${err.message}: ${err.body}`;
      } else {
        this.saveError = err instanceof Error ? err.message : String(err);
      }
    } finally {
      this.saving = false;
    }
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
