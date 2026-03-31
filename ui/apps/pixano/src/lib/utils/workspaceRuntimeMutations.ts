/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { annotations, entities, itemMetas, views } from "$lib/stores/workspaceStores.svelte";
import { WorkspaceType, type Annotation, type Entity } from "$lib/types/dataset";
import { normalizeWorkspaceRuntimeState } from "$lib/utils/workspaceRuntime";

export function commitNormalizedWorkspaceRuntime(
  nextAnnotations: Annotation[],
  nextEntities: Entity[],
): { annotations: Annotation[]; entities: Entity[] } {
  const workspaceType = itemMetas.value?.type ?? WorkspaceType.UNDEFINED;
  const normalized = normalizeWorkspaceRuntimeState(
    {
      annotations: nextAnnotations,
      entities: nextEntities,
    },
    workspaceType,
    views.value,
  );
  annotations.value = normalized.annotations;
  entities.value = normalized.entities;
  return normalized;
}
