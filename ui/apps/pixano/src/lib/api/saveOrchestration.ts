/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ApiError } from "./apiClient";
import type { ResourceMutation } from "./resourcePayloads";
import { createResource, deleteResource, updateResource, type StoredRow } from "./schemaApi";
import type { SaveQueue } from "$lib/stores/saveQueue";

const NOT_FOUND = 404;

/**
 * Called with each mutation once the server stored it, and the row it answered with: none for a
 * delete. It runs between two writes, so it only notes what it needs.
 */
export type OnPersisted = (mutation: ResourceMutation, stored: StoredRow | undefined) => void;

/** Called with an update dropped because its row is gone: the screen still shows the row. */
export type OnGone = (mutation: ResourceMutation) => void;

function errorDetail(error: ApiError): { code?: string; message?: string } {
  try {
    const body = JSON.parse(error.body) as {
      detail?: string | { code?: string; message?: string };
    };
    return typeof body.detail === "string" ? { message: body.detail } : (body.detail ?? {});
  } catch {
    return {};
  }
}

export function saveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = errorDetail(error);
    if (detail.code === "id_conflict") {
      return "Saving stopped because an existing annotation has different data. Your remaining changes are still staged.";
    }
    if (detail.code === "dataset_busy" || detail.code === "dataset_replaced") {
      return detail.message ?? "The dataset is busy. Your changes are still staged; try again.";
    }
    if (detail.message)
      return `Saving failed: ${detail.message} Your remaining changes are still staged.`;
  }
  return "Saving failed — your remaining changes are still staged. Try again.";
}

/**
 * Whether the row an update was for no longer exists: deleted since it was read, or replaced by a
 * model's run. The update cannot land anywhere; queued again, it would block every later write.
 * The server names the row it did not find: a 404 that names none, as for a dataset gone, is not
 * one.
 */
function updatesARowGone(mutation: ResourceMutation, error: unknown): boolean {
  if (mutation.op !== "update" || !(error instanceof ApiError) || error.status !== NOT_FOUND) {
    return false;
  }
  return errorDetail(error).message?.includes(`'${mutation.target.id}'`) ?? false;
}

/**
 * Tell the caller of a write's outcome. What it makes of it is no part of the save: the write is
 * settled, and the rest of the record still to save.
 */
function tellCaller(notify: () => void): void {
  try {
    notify();
  } catch (error) {
    console.error(error);
  }
}

function knownNotWritten(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (error.status === 409) return errorDetail(error).code === "dataset_busy";
  return [400, 401, 403, 404, 405, 422, 423, 429].includes(error.status);
}

async function persistMutation(
  mutation: ResourceMutation,
  datasetId: string,
): Promise<StoredRow | undefined> {
  if (mutation.op === "create") {
    return createResource(datasetId, mutation.target.resource, mutation.table, mutation.body ?? {});
  }
  if (mutation.op === "update") {
    return updateResource(
      datasetId,
      mutation.target.resource,
      mutation.table,
      mutation.target.id,
      mutation.body ?? {},
    );
  }
  await deleteResource(datasetId, mutation.target.resource, mutation.table, mutation.target.id);
  return undefined;
}

/**
 * Acknowledge only completed requests; retain uncertain payloads for an identical retry.
 *
 * @param onPersisted Told of each mutation once it is stored and acknowledged; never of one the
 *   queue no longer holds, as after leaving the record (`SaveQueue.reset`).
 * @param onGone Told of each update dropped because its row is gone.
 */
export async function persistSaveItems(
  queue: SaveQueue,
  datasetId: string,
  onPersisted?: OnPersisted,
  onGone?: OnGone,
): Promise<void> {
  const generation = queue.generation;
  while (queue.generation === generation) {
    const attempt = queue.next();
    if (!attempt) return;
    let stored: StoredRow | undefined;
    try {
      stored = await persistMutation(attempt.mutation, datasetId);
    } catch (error) {
      if (updatesARowGone(attempt.mutation, error)) {
        // Dropped, as a delete of a row already gone is: the rest of the record is saved.
        if (!queue.acknowledge(attempt)) return;
        tellCaller(() => onGone?.(attempt.mutation));
        continue;
      }
      queue.fail(attempt, knownNotWritten(error) ? "unchanged" : "unknown");
      throw error;
    }
    if (!queue.acknowledge(attempt)) return;
    tellCaller(() => onPersisted?.(attempt.mutation, stored));
  }
}
