/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ApiError } from "./apiClient";
import type { ResourceMutation } from "./resourcePayloads";
import { createResource, deleteResource, updateResource } from "./schemaApi";
import type { SaveQueue } from "$lib/stores/saveQueue";

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

function knownNotWritten(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (error.status === 409) return errorDetail(error).code === "dataset_busy";
  return [400, 401, 403, 404, 405, 422, 423, 429].includes(error.status);
}

async function persistMutation(mutation: ResourceMutation, datasetId: string): Promise<void> {
  if (mutation.op === "create") {
    await createResource(datasetId, mutation.target.resource, mutation.table, mutation.body ?? {});
  } else if (mutation.op === "update") {
    await updateResource(
      datasetId,
      mutation.target.resource,
      mutation.table,
      mutation.target.id,
      mutation.body ?? {},
    );
  } else {
    await deleteResource(datasetId, mutation.target.resource, mutation.table, mutation.target.id);
  }
}

/** Acknowledge only completed requests; retain uncertain payloads for an identical retry. */
export async function persistSaveItems(queue: SaveQueue, datasetId: string): Promise<void> {
  const generation = queue.generation;
  while (queue.generation === generation) {
    const attempt = queue.next();
    if (!attempt) return;
    try {
      await persistMutation(attempt.mutation, datasetId);
    } catch (error) {
      queue.fail(attempt, knownNotWritten(error) ? "unchanged" : "unknown");
      throw error;
    }
    if (!queue.acknowledge(attempt)) return;
  }
}
