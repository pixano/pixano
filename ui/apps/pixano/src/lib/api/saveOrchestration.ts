/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

 import { BaseSchema } from "$lib/types/dataset";

 import type { ResourceMutation } from "./resourcePayloads";
import { createResource, deleteResource, updateResource } from "./schemaApi";

function mutationPriority(mutation: ResourceMutation): number {
  if (mutation.op === "delete") {
    if (mutation.schema.table_info.base_schema === BaseSchema.Entity) return 4;
    if (mutation.schema.table_info.base_schema === BaseSchema.Tracklet) return 3;
    return 2;
  }

  if (mutation.schema.table_info.base_schema === BaseSchema.Entity) return 0;
  if (mutation.schema.table_info.base_schema === BaseSchema.Tracklet) return 1;
  return 2;
}

function sortMutations(mutations: ResourceMutation[]): ResourceMutation[] {
  return [...mutations].sort((a, b) => mutationPriority(a) - mutationPriority(b));
}

export async function persistSaveItems(mutations: ResourceMutation[], datasetId: string): Promise<void> {
  const orderedMutations = sortMutations(mutations);

  for (const mutation of orderedMutations) {
    if (mutation.op === "create") {
      await createResource(
        datasetId,
        mutation.target.resource,
        mutation.schema.table_info.name,
        mutation.body ?? {},
      );
      continue;
    }

    if (mutation.op === "update") {
      await updateResource(
        datasetId,
        mutation.target.resource,
        mutation.schema.table_info.name,
        mutation.target.id,
        mutation.body ?? {},
      );
      continue;
    }

    await deleteResource(
      datasetId,
      mutation.target.resource,
      mutation.schema.table_info.name,
      mutation.target.id,
    );
  }
}
