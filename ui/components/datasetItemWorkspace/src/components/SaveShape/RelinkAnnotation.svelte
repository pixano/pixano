<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";

  import { Annotation, BaseSchema, Entity, Tracklet, type Reference } from "@pixano/core";

  import { NEWTRACKLET_LENGTH } from "../../lib/constants";
  import { getDefaultDisplayFeat } from "../../lib/settings/defaultFeatures";
  import { colorScale, entities } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";

  export let selectedEntityId: string = "new";
  export let viewRef: Reference;
  export let tracklet: Annotation | null = null;

  const isEntityAllowedAsTop = (entity: Entity) => {
    const isTopEntity = entity.data.parent_ref.id === "";
    if (!isTopEntity) return false;
    if (entity.is_conversation) return false;
    const tracklets = entity.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Tracklet));
    if (tracklet && tracklet.is_type(BaseSchema.Tracklet)) {
      const overlap = tracklets?.some(
        (ann) =>
          (ann as Tracklet).data.view_ref.name === viewRef.name &&
          (ann as Tracklet).data.start_timestep < (tracklet as Tracklet).data.end_timestep &&
          (ann as Tracklet).data.end_timestep > (tracklet as Tracklet).data.start_timestep,
      );
      return !overlap;
    } else {
      const overlap = tracklets?.some(
        (ann) =>
          (ann as Tracklet).data.view_ref.name === viewRef.name &&
          (ann as Tracklet).data.start_timestep < $currentFrameIndex + NEWTRACKLET_LENGTH + 1 &&
          (ann as Tracklet).data.end_timestep > $currentFrameIndex,
      );
      return !overlap;
    }
  };

  let entitiesCombo = derived([entities], ([$entities]) => {
    const res: { id: string; name: string; color: string }[] = [
      { id: "new", name: "New", color: "" },
    ];
    $entities.forEach((entity) => {
      //check if there is no annotation of same kind & view_id for this entity
      if (isEntityAllowedAsTop(entity)) {
        const displayFeat = getDefaultDisplayFeat(entity);
        res.push({
          id: entity.id,
          name: displayFeat ? `${displayFeat} (${entity.id})` : entity.id,
          color: `${$colorScale[1](entity.id)}3a`,
        });
      }
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
      {#each $entitiesCombo as { id, name, color }}
        <option value={id} style="background: {color};">
          {name}
        </option>
      {/each}
    </select>
  </div>
{/if}
