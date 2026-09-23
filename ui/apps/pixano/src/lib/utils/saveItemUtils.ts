/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toResourceMutation, type ResourceMutation } from "$lib/api/resourcePayloads";
import { workspaceSaveQueue } from "$lib/stores/workspaceStores.svelte";
import type { SaveItem, Schema } from "$lib/types/dataset";

function toMutationOp(changeType: SaveItem["change_type"]): ResourceMutation["op"] {
  if (changeType === "add") return "create";
  return changeType;
}

export function saveTo(changeType: SaveItem["change_type"], data: Schema): void {
  workspaceSaveQueue.stage(toResourceMutation(toMutationOp(changeType), data));
}
