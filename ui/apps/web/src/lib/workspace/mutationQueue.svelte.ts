/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { sortMutations } from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import { ApiError } from "$lib/api/apiClient.js";

import type { MutationGateway } from "./datasetGateway.js";
import type { WorkspaceSession } from "./workspaceSession.svelte.js";

/**
 * Lookup the queue uses to mark a `LocalBBox` as persisted after a
 * successful create. The queue stays widget-storage-agnostic; the wiring
 * code that constructs the queue supplies a closure that knows where to
 * look.
 *
 * Returning `undefined` is fine — it just means the storage was already
 * cleared (e.g. user navigated away mid-flush) and the persistence flag
 * doesn't need flipping.
 */
export interface LocalBBoxLocator {
  findLocalBBox(
    widgetId: string,
    localBBoxId: string,
  ): { persisted: boolean } | undefined;
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
    private locator: LocalBBoxLocator,
  ) {}

  /** Append a mutation to the queue. Order matters; `flush` re-orders only
   * by resource (entities first, then bboxes, deletes last) via
   * `sortMutations` — within a resource the original order is preserved. */
  queue(mutation: ResourceMutation): void {
    this.pending.push(mutation);
  }

  /**
   * Drop every queued mutation that references the given local bbox id.
   * Used when a bbox is deleted locally before it has been persisted, so
   * we don't POST-then-DELETE it for nothing.
   */
  dropForLocalBBox(localBBoxId: string): ResourceMutation[] {
    const dropped: ResourceMutation[] = [];
    this.pending = this.pending.filter((m) => {
      if (m.localBBoxId === localBBoxId) {
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
   * before the bboxes that reference them; deletes run last. On success,
   * the corresponding `LocalBBox` (if any) is marked `persisted: true`
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

    const ordered = sortMutations(this.pending);

    try {
      for (const mutation of ordered) {
        await this.run(datasetId, mutation);
        if (
          mutation.op === "create" &&
          mutation.resource === "bboxes" &&
          mutation.widgetId &&
          mutation.localBBoxId
        ) {
          const bbox = this.locator.findLocalBBox(
            mutation.widgetId,
            mutation.localBBoxId,
          );
          if (bbox) bbox.persisted = true;
        }
      }
      this.pending = [];
    } catch (err) {
      if (err instanceof ApiError) {
        // Surface the backend's `detail` so the user can see why the
        // request was rejected (e.g. "Invalid data: <field> extra inputs
        // are not permitted" or "Foreign key violation: record_id=…").
        console.error("flushSave - failing mutation body:", err.body);
        this.saveError = `${err.message}: ${err.body}`;
      } else {
        this.saveError = err instanceof Error ? err.message : String(err);
      }
    } finally {
      this.saving = false;
    }
  }

  private async run(datasetId: string, mutation: ResourceMutation): Promise<void> {
    if (mutation.op === "create" && mutation.resource === "entities") {
      console.debug("flushSave -> POST entities", mutation.body);
      await this.gateway.createEntity(datasetId, mutation.body);
      return;
    }
    if (mutation.op === "create" && mutation.resource === "bboxes") {
      console.debug("flushSave -> POST bboxes", mutation.body);
      await this.gateway.createBBox(datasetId, mutation.body);
      return;
    }
    if (mutation.op === "update" && mutation.resource === "bboxes") {
      await this.gateway.updateBBox(datasetId, mutation.id, mutation.body);
      return;
    }
    if (mutation.op === "delete" && mutation.resource === "bboxes") {
      await this.gateway.deleteBBox(datasetId, mutation.id);
      return;
    }
    if (mutation.op === "delete" && mutation.resource === "entities") {
      await this.gateway.deleteEntity(datasetId, mutation.id);
      return;
    }
  }
}
