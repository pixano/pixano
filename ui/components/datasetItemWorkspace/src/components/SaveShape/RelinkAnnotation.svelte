<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";

  import { BaseSchema, Entity, Tracklet, type Reference } from "@pixano/core";

  import { NEWTRACKLET_LENGTH } from "../../lib/constants";
  import { entities } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";

  export let selectedEntityId: string = "new";
  export let baseSchema: BaseSchema;
  export let viewRef: Reference;

  const isEntityAllowedAsTop = (entity: Entity) => {
    const isTopEntity = entity.data.parent_ref.id === "";
    if (!isTopEntity) return false;
    if (entity.is_conversation) return false;
    const annsNotTracklets = entity.ui.childs?.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
    const sameKindInSameView = annsNotTracklets?.some(
      (ann) => ann.data.view_ref.id === viewRef.id && baseSchema === ann.table_info.base_schema,
    );
    const tracklets = entity.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Tracklet));
    const overlap = tracklets?.some(
      (ann) =>
        (ann as Tracklet).data.view_ref.name === viewRef.name &&
        (ann as Tracklet).data.start_timestep < $currentFrameIndex + NEWTRACKLET_LENGTH + 1 &&
        (ann as Tracklet).data.end_timestep > $currentFrameIndex,
    );
    return !sameKindInSameView && !overlap;
  };

  let entitiesCombo = derived([entities], ([$entities]) => {
    const res: { id: string; name: string }[] = [{ id: "new", name: "New" }];
    $entities.forEach((entity) => {
      //check if there is no annotation of same kind & view_id for this entity
      if (isEntityAllowedAsTop(entity))
        res.push({ id: entity.id, name: (entity.data.name as string) + " - " + entity.id });
    });
    selectedEntityId = res[0].id;
    return res;
  });
</script>

{#if $entitiesCombo.length > 0}
  <div>
    <span>Select parent entity</span>
    <select
      class="w-full py-1 px-2 border rounded focus:outline-none
bg-slate-100 border-slate-300 focus:border-main"
      bind:value={selectedEntityId}
    >
      {#each $entitiesCombo as { id, name }}
        <option value={id}>
          {name}
        </option>
      {/each}
    </select>
  </div>
{/if}
