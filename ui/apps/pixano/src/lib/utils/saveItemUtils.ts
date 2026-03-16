/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toResourceMutation, type ResourceMutation } from "$lib/api/resourcePayloads";
import { saveData } from "$lib/stores/workspaceStores.svelte";
import type { SaveItem, Schema } from "$lib/types/dataset";

function sameTarget(left: ResourceMutation, right: ResourceMutation): boolean {
  return left.target.resource === right.target.resource && left.target.id === right.target.id;
}

function normalizeMutation(
  existing: ResourceMutation | undefined,
  incoming: ResourceMutation,
): ResourceMutation | undefined {
  if (!existing) {
    return incoming;
  }

  if (existing.op === "create") {
    if (incoming.op === "delete") return undefined;
    return { ...incoming, op: "create" };
  }

  if (existing.op === "update") {
    if (incoming.op === "delete") return incoming;
    if (incoming.op === "update") return incoming;
    console.error("Invalid mutation transition: update -> create", existing, incoming);
    return existing;
  }

  if (incoming.op !== "delete") {
    console.error("Invalid mutation transition: delete terminal", existing, incoming);
  }
  return existing;
}

export const addOrUpdateSaveItem = (
  mutations: ResourceMutation[],
  incoming: ResourceMutation,
): ResourceMutation[] => {
  const existing = mutations.find((mutation) => sameTarget(mutation, incoming));
  const remaining = mutations.filter((mutation) => !sameTarget(mutation, incoming));
  const normalized = normalizeMutation(existing, incoming);
  if (!normalized) {
    return remaining;
  }
  remaining.push(normalized);
  return remaining;
};

function toMutationOp(changeType: SaveItem["change_type"]): ResourceMutation["op"] {
  if (changeType === "add") return "create";
  return changeType;
}

export function saveTo(changeType: SaveItem["change_type"], data: Schema): void {
  saveData.update((mutations) =>
    addOrUpdateSaveItem(mutations, toResourceMutation(toMutationOp(changeType), data)),
  );
}
