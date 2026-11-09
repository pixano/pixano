/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MutationGateway } from "./datasetGateway.js";
import type { WorkspaceSession } from "./workspaceSession.svelte.js";
import { sortMutations } from "$lib/annotations/buildPayloads.js";
import type { ResourceMutation } from "$lib/annotations/types.js";
import type { EntityDeleteAnswer } from "$lib/api/annotations.js";
import { ApiError, isRefusal } from "$lib/api/apiClient.js";
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
  /**
   * Told each time a body is written into the queue — a mutation queued, or a
   * queued body rewritten by a later gesture — with the mutation as the queue
   * holds it. The body leaves later, when its annotation may have been edited
   * again, so the owner of the annotations keeps here what this body carries.
   */
  recordQueued?(mutation: ResourceMutation): void;
  /**
   * Told as each mutation leaves for the backend, so the owner of the
   * annotations can record what the dataset holds once it lands. Returns how to
   * undo that record if the write fails.
   */
  recordWrite?(mutation: ResourceMutation): (() => void) | undefined;
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
   * How many writes have reached the backend so far: each one answered, and
   * each one that failed without the server refusing it — after a network
   * error or a 5xx, it may have been stored before its answer was lost. A read
   * of the record begun before the latest one may hold rows older than what
   * that write stored, and is not to be trusted (`WorkspaceManager.readBack`).
   * A write the server refused (a 4xx) stored nothing, and is not counted.
   */
  writesLanded = 0;

  /**
   * Bumped by `reset`, so that a request still in flight when the queue was
   * abandoned — another record opened — neither comes back into the new
   * record's queue on failure nor reports its error there.
   */
  private generation = 0;

  /**
   * The creates on the wire that nothing wants any more — a draft deleted, an
   * entity nothing names now — each with the delete queued to undo what it
   * makes once it lands. Should the server refuse the create, it made nothing:
   * that delete is dropped. Should it fail any other way, it may have made it:
   * the delete stays queued, and the create is not tried again.
   */
  private abandoned = new Map<ResourceMutation, ResourceMutation>();

  /**
   * The entities this queue's creates may have made — sent, and not refused —
   * that no write the server may have stored names yet, by id, each with its
   * create. Changing one's mind about an entity must not leave it in the
   * dataset: one that nothing queued names any more has a delete queued
   * (`settleSentEntities`), which the server applies only if nothing names it
   * (`MutationGateway.deleteEntity`). Once a write naming it lands, or fails in
   * a way that may have stored it, a row may name it: it is no longer this
   * queue's to delete, and the server prunes it when that row lets go of it.
   */
  private sentEntities = new Map<string, EntityCreate>();

  /**
   * The entities this queue's deletes may have removed — answered deleted, or
   * failed in a way that may have deleted them — by id, each with its create.
   * A write may name one again: one queued while its delete was on the wire,
   * or one picked from a list read before. That write sends the create first
   * (`sendIfStillQueued`), which the server takes as a retry should the entity
   * still be there. The entity stays here until that create lands: one that
   * fails is not queued — no gesture's to drop — but sent again before the
   * next write naming the entity.
   */
  private deletedEntities = new Map<string, EntityCreate>();

  /**
   * The creates that failed in a way that may have stored them, each with the
   * create of the entity it names, which the queue let go of then (`failed`).
   * Should the server refuse one later, that entity is the queue's to delete
   * again (`storedNothing`).
   */
  private uncertainCreates = new Map<ResourceMutation, EntityCreate>();

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
    // It may name an entity whose delete is queued, as a draft linked to an
    // entity picked from the list does: that delete is dropped.
    this.settleSentEntities();
  }

  /** Whether any write of this annotation is queued or on the wire. */
  holdsWorkFor(localAnnotationId: string): boolean {
    return (
      this.inFlight?.localAnnotationId === localAnnotationId ||
      this.pending.some((m) => m.localAnnotationId === localAnnotationId)
    );
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
      this.locator.recordQueued?.(existing);
    } else {
      this.append(mutation);
    }
    // The body replaced may have named an entity this one does not.
    this.settleSentEntities();
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
      this.locator.recordQueued?.(pending);
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
   * Forget an entity this annotation was going to be moved onto, because the
   * user then picked a different one.
   *
   * Changing your mind twice before saving used to leave the first entity
   * behind: `upsertUpdate` replaces the annotation's update so only the last
   * choice is referenced, but the creates piled up, and the abandoned one was
   * written to the dataset with nothing pointing at it. Correcting a mistake
   * should not litter. An entity whose create has already left has a delete
   * queued instead, once nothing names it (`settleSentEntities`).
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
    this.settleSentEntities();
  }

  /**
   * Drop every queued mutation that references the given local annotation id.
   * Used when an annotation is deleted locally: a draft, so we don't
   * POST-then-DELETE it for nothing, and a stored row before its delete is
   * queued, whose update — and the create of an entity a reassignment queued
   * for it — would only be sent to be undone.
   *
   * What has already left cannot be called back. A draft's create on the wire:
   * the row it makes is deleted once it lands. So dropping a draft while its
   * create is on the wire never leaves it in the dataset — unless the queue is
   * reset (Discard, another record) before that delete is sent. A create that
   * failed without a refusal is back in the queue, and dropped here as any
   * queued create: it may have stored its row before its answer was lost, and
   * that row stays in the dataset.
   *
   * An entity made for the annotation, sent and named by nothing any more: it
   * has a delete queued (`settleSentEntities`). So dropping a draft does not,
   * as a rule, leave the entity made for it in the dataset — nor does an edit
   * thrown away leave the entity it had moved the annotation onto. The
   * exception is an entity named by a write that failed without the server
   * refusing it: that write may have been stored, and the entity is left where
   * it is (`failed`). A reset of the queue (Discard, another record) before
   * these deletes are sent drops them with the rest of the unsaved work.
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
    const sending = this.inFlight;
    const sentId = sending?.op === "create" ? sending.body.id : undefined;
    if (
      sending?.localAnnotationId === localAnnotationId &&
      sending.resource !== ENTITY_RESOURCE &&
      typeof sentId === "string"
    ) {
      const compensation = this.append({
        op: "delete",
        resource: sending.resource,
        id: sentId,
        widgetId: sending.widgetId,
        localAnnotationId,
      });
      this.abandoned.set(sending, compensation);
    }
    this.settleSentEntities();
    return dropped;
  }

  /** Reset the queue without flushing. Used when clearing the workspace. */
  reset(): void {
    this.pending = [];
    this.saveError = null;
    this.abandoned.clear();
    this.sentEntities.clear();
    this.deletedEntities.clear();
    this.uncertainCreates.clear();
    this.generation++;
  }

  /**
   * Flush every queued mutation to the backend. Entities are created
   * before the annotations that reference them; deletes run last. On success,
   * the corresponding local annotation (if any) is marked `persisted: true`
   * via the locator the manager provided.
   *
   * Sends what was queued when it began, and of it only what is still queued
   * when its turn comes (`sendIfStillQueued`). A gesture made meanwhile can
   * still rewrite a queued body this save is about to send — moving that
   * annotation onto an entity created for it, whose create was queued after the
   * save began. That create is sent first, so no write names an entity that
   * does not exist yet. The deletes of entities nothing names any more are the
   * last it sends (`sortMutations`): every write naming one is sent before.
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
    // this.pending, so a mutation dropped meanwhile is recognised by identity.
    const toProcess = sortMutations([...this.pending]);

    try {
      for (const mutation of toProcess) {
        await this.sendIfStillQueued(datasetId, mutation, generation);
      }
    } catch (err) {
      if (generation === this.generation) this.saveError = describeFailure(err);
    } finally {
      this.saving = false;
    }
  }

  /**
   * Send one write of a flush, if it is still queued — preceded by the create
   * of the entity it names when that create is queued too: one queued after
   * the flush began, by the gesture that moved the annotation onto it. Or when
   * this queue's delete may have removed that entity (`deletedEntities`): the
   * write was queued while the delete was on the wire, or names the entity
   * from a list read before it.
   *
   * Every request is awaited, and a gesture made meanwhile may drop the write
   * (a change of mind, a draft deleted), rewrite it to name another new entity,
   * or reset the queue (Discard, another record). So it is looked at again
   * after each one: a write dropped is not sent, and one rewritten waits for
   * the create of the entity it names now, until none is left to send first.
   */
  private async sendIfStillQueued(
    datasetId: string,
    mutation: ResourceMutation,
    generation: number,
  ): Promise<void> {
    for (;;) {
      if (generation !== this.generation || !this.pending.includes(mutation)) return;
      const entityCreate = this.entityCreateToSendBefore(mutation);
      if (!entityCreate) break;
      await this.send(datasetId, entityCreate, generation);
    }
    await this.send(datasetId, mutation, generation);
  }

  /**
   * The create of the entity this write names, when it must be sent first: one
   * queued, or — for an entity this queue's delete may have removed — a copy of
   * the create that made it.
   */
  private entityCreateToSendBefore(mutation: ResourceMutation): ResourceMutation | undefined {
    const entityId = entityNamedBy(mutation);
    if (entityId === undefined) return undefined;
    const queued = this.pending.find((m) => createdEntityId(m) === entityId);
    if (queued) return queued;
    const deleted = this.deletedEntities.get(entityId);
    // A copy: the create sent before is known by identity (`abandoned`).
    return deleted && { ...deleted, body: { ...deleted.body } };
  }

  /** Append to the queue, telling the locator; returns the mutation as the queue holds it. */
  private append(mutation: ResourceMutation): ResourceMutation {
    this.pending.push(mutation);
    // Read back rather than returned as given: the queue holds its own
    // reactive copy, the object `flush` sends and identifies by reference.
    const held = this.pending[this.pending.length - 1];
    this.locator.recordQueued?.(held);
    return held;
  }

  /**
   * Send one mutation. It leaves `pending` as its request leaves, so nothing
   * queued meanwhile can be written into it, and comes back at the head of the
   * queue if the request fails — unless the queue was reset meanwhile, or
   * nothing wants what it makes any more (`abandoned`): then there is nothing
   * to retry.
   */
  private async send(
    datasetId: string,
    mutation: ResourceMutation,
    generation: number,
  ): Promise<void> {
    this.pending = this.pending.filter((m) => m !== mutation);
    this.inFlight = mutation;
    const entityId = createdEntityId(mutation);
    if (mutation.op === "create" && entityId !== undefined) {
      this.sentEntities.set(entityId, mutation);
    }
    const undoRecord = this.locator.recordWrite?.(mutation);
    let answer: EntityDeleteAnswer | void;
    try {
      answer = await this.run(datasetId, mutation);
    } catch (err) {
      this.inFlight = null;
      undoRecord?.();
      this.failed(mutation, err, generation);
      return;
    }
    this.inFlight = null;
    this.writesLanded++;
    this.landed(mutation, answer);
  }

  /**
   * What a write that landed leaves to do.
   *
   * @param mutation The write.
   * @param answer The server's answer to an entity delete; nothing for any
   *   other write.
   */
  private landed(mutation: ResourceMutation, answer: EntityDeleteAnswer | void): void {
    this.abandoned.delete(mutation);
    this.uncertainCreates.delete(mutation);
    const created = createdEntityId(mutation);
    if (created !== undefined) this.deletedEntities.delete(created);
    // A stored row names this entity now: the server prunes it when that row
    // lets go of it. It is no longer this queue's to delete.
    const named = entityNamedBy(mutation);
    if (named !== undefined) this.sentEntities.delete(named);
    if (isEntityDelete(mutation)) {
      this.entityDeleteAnswered(mutation.id, answer ? answer.deleted : true);
    }
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
   * What an entity delete answered leaves to do. Gone, the entity may be named
   * again — by a write queued while the delete was on the wire — and that
   * write then sends its create first. Kept, something stored names it. Either
   * way it is no longer this queue's to delete.
   */
  private entityDeleteAnswered(entityId: string, gone: boolean): void {
    const create = this.sentEntities.get(entityId);
    this.sentEntities.delete(entityId);
    if (gone && create) this.deletedEntities.set(entityId, create);
    else this.deletedEntities.delete(entityId);
  }

  /**
   * What a write that failed leaves to do; throws its error, unless nothing is
   * left of it to report.
   *
   * A refusal — a 4xx (`isRefusal`) — says the server stored nothing. Any other
   * failure says nothing of the kind: it may have stored the write before the
   * answer was lost. So it counts as landed for the reads begun before it, and
   * a row may name the entity the write names: that entity is no longer this
   * queue's to delete, whatever becomes of the write. An entity delete that
   * failed so may have deleted the entity.
   *
   * A create nothing wants any more (`abandoned`) is not tried again. Refused,
   * it made nothing: the delete queued to undo it is dropped, and there is no
   * failure to report. Otherwise that delete stays queued — answered "not
   * found" if nothing was made — and the failure is reported. A create that
   * failed no longer names its entity: one made for it nothing else names has
   * a delete queued (`settleSentEntities`) — unless it may have been stored.
   *
   * Any other write comes back at the head of the queue, unless the queue was
   * reset meanwhile, or it creates again an entity this queue's delete may
   * have removed (`deletedEntities`): that one is sent again before the next
   * write naming the entity.
   */
  private failed(mutation: ResourceMutation, err: unknown, generation: number): void {
    const refused = isRefusal(err);
    if (refused) this.storedNothing(mutation);
    else this.mayHaveStored(mutation);
    const compensation = this.abandoned.get(mutation);
    if (compensation !== undefined) {
      this.abandoned.delete(mutation);
      if (refused) this.pending = this.pending.filter((m) => m !== compensation);
      this.settleSentEntities();
      if (refused) return;
      throw err;
    }
    if (generation === this.generation && !this.isRecreation(mutation)) {
      this.pending = [mutation, ...this.pending];
    }
    // An entity delete back in the queue may meet a write that names the
    // entity again: that delete is dropped.
    this.settleSentEntities();
    throw err;
  }

  /**
   * Whether this write creates again an entity this queue's delete may have
   * removed — sent from `deletedEntities`, where it stays until it lands.
   */
  private isRecreation(mutation: ResourceMutation): boolean {
    const entityId = createdEntityId(mutation);
    return entityId !== undefined && this.deletedEntities.has(entityId);
  }

  /**
   * A write the server refused stored nothing; an entity create made nothing.
   * A create the server refuses after it failed in a way that may have stored
   * it gives the entity it names back to the queue (`uncertainCreates`): a
   * change of mind then deletes it, as for any create. Its first try may still
   * have stored a row — a refusal of the retry, such as a busy dataset's 409,
   * does not say — but the delete is one the server applies only if nothing
   * names the entity, so such a row keeps it.
   */
  private storedNothing(mutation: ResourceMutation): void {
    const entityId = createdEntityId(mutation);
    if (entityId !== undefined) this.sentEntities.delete(entityId);
    const entityCreate = this.uncertainCreates.get(mutation);
    if (entityCreate === undefined) return;
    this.uncertainCreates.delete(mutation);
    const named = createdEntityId(entityCreate);
    if (named !== undefined && !this.sentEntities.has(named)) {
      this.sentEntities.set(named, entityCreate);
    }
  }

  /**
   * A write that failed without a refusal may have been stored: it counts as
   * landed for the reads begun before it (`writesLanded`). The entity it names
   * may be named by its row now, so the queue lets go of it — a create keeps it
   * in `uncertainCreates` until the server says more. An entity delete may
   * have removed its entity (`deletedEntities`).
   */
  private mayHaveStored(mutation: ResourceMutation): void {
    this.writesLanded++;
    const named = entityNamedBy(mutation);
    const entityCreate = named === undefined ? undefined : this.sentEntities.get(named);
    if (named !== undefined && entityCreate !== undefined) {
      this.sentEntities.delete(named);
      if (mutation.op === "create") this.uncertainCreates.set(mutation, entityCreate);
    }
    if (isEntityDelete(mutation)) {
      const deletedCreate = this.sentEntities.get(mutation.id);
      if (deletedCreate !== undefined) this.deletedEntities.set(mutation.id, deletedCreate);
    }
  }

  /**
   * Undo, or stop undoing, each entity this queue's creates may have made that
   * no stored row may name yet (`sentEntities`), by what is queued now. One
   * that nothing queued or on the wire names any more — a reassignment changed
   * its mind, a delete threw the edit away, a draft was deleted, its create
   * failed — has a delete queued, which the server applies only if nothing
   * names the entity; should its create be on the wire, that create is
   * abandoned. One named again before that delete left has the delete dropped.
   * One named again while it is on the wire waits for its answer
   * (`entityDeleteAnswered`).
   */
  private settleSentEntities(): void {
    const deletes = (m: ResourceMutation | null, entityId: string) =>
      m !== null && isEntityDelete(m) && m.id === entityId;
    for (const [entityId, create] of this.sentEntities) {
      const queuedDelete = this.pending.find((m) => deletes(m, entityId));
      const named = this.namesEntity(entityId);
      if (named && queuedDelete) {
        this.pending = this.pending.filter((m) => m !== queuedDelete);
        if (this.abandoned.get(create) === queuedDelete) this.abandoned.delete(create);
        continue;
      }
      if (named || queuedDelete || deletes(this.inFlight, entityId)) continue;
      const compensation = this.append({
        op: "delete",
        resource: ENTITY_RESOURCE,
        id: entityId,
        widgetId: create.widgetId,
        localAnnotationId: create.localAnnotationId,
      });
      if (this.inFlight === create) this.abandoned.set(create, compensation);
    }
  }

  /** Whether a write queued or on the wire names this entity. */
  private namesEntity(entityId: string): boolean {
    const names = (m: ResourceMutation) => entityNamedBy(m) === entityId;
    return (this.inFlight !== null && names(this.inFlight)) || this.pending.some(names);
  }

  /** Send one write; resolves the server's answer to an entity delete. */
  private async run(
    datasetId: string,
    mutation: ResourceMutation,
  ): Promise<EntityDeleteAnswer | void> {
    if (mutation.resource === ENTITY_RESOURCE) {
      if (mutation.op === "create") {
        await this.gateway.createEntity(datasetId, mutation.body);
      } else if (mutation.op === "delete") {
        return this.gateway.deleteEntity(datasetId, mutation.id);
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
 * The column through which an annotation row names its entity — every entity
 * annotation table has it, and the server checks that it names one on write.
 */
const ENTITY_REFERENCE_FIELD = "entity_id";

/** A write creating an entity — what this queue keeps of each entity it made. */
type EntityCreate = Extract<ResourceMutation, { op: "create" }>;

/** The id of the entity this write creates, if it creates one. */
function createdEntityId(mutation: ResourceMutation): string | undefined {
  if (mutation.op !== "create" || mutation.resource !== ENTITY_RESOURCE) return undefined;
  const id = mutation.body.id;
  return typeof id === "string" ? id : undefined;
}

/**
 * The entity an annotation's create or update names, if any. Read when asked:
 * a queued body may be rewritten by a later gesture.
 */
function entityNamedBy(mutation: ResourceMutation): string | undefined {
  if (mutation.op === "delete" || mutation.resource === ENTITY_RESOURCE) return undefined;
  const id = mutation.body[ENTITY_REFERENCE_FIELD];
  return typeof id === "string" ? id : undefined;
}

function isEntityDelete(
  mutation: ResourceMutation,
): mutation is Extract<ResourceMutation, { op: "delete" }> {
  return mutation.op === "delete" && mutation.resource === ENTITY_RESOURCE;
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
