<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";

  import { Annotation, BaseSchema, Entity, Tracklet, type Reference } from "@pixano/core";

  import { getTopEntity } from "../../lib/api/objectsApi";
  import { getDefaultDisplayFeat } from "../../lib/settings/defaultFeatures";
  import { colorScale, entities } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";

  export let selectedEntityId: string = "new";
  export let mustMerge: boolean = false;
  export let overlapTargetId: string = "";
  export let baseSchema: BaseSchema;
  export let viewRef: Reference;
  export let tracklet: Annotation | null = null;

  const entityAllowInfo = (
    entity: Entity,
  ): {
    hard_forbidden: boolean;
    overlap: boolean;
    numSameKindInSameView: number;
    overlapTargetId: string;
  } => {
    if (
      entity.data.parent_ref.id !== "" ||
      entity.is_conversation ||
      (tracklet && getTopEntity(tracklet).id === entity.id)
    )
      return {
        hard_forbidden: true,
        overlap: false,
        numSameKindInSameView: 0,
        overlapTargetId: "",
      };
    const tracklets = entity.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Tracklet));
    const annsNotTracklets = entity.ui.childs?.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
    let numSameKindInSameView: number = 0;
    let overlap: boolean | undefined = undefined;
    let overlapTargetId: string = "";
    if (tracklet && tracklet.is_type(BaseSchema.Tracklet)) {
      const trackletBaseSchemaByFrameIndex = (tracklet as Tracklet).ui.childs.reduce(
        (acc, ann) => {
          if (ann.ui.frame_index) {
            acc[ann.ui.frame_index] = ann.table_info.base_schema;
          }
          return acc;
        },
        {} as Record<number, BaseSchema>,
      );
      const sameKindInSameView_anns = annsNotTracklets?.filter(
        //NOTE we "miss" interpolated shapes. So we can "insert"
        (ann) =>
          ann.ui.frame_index
            ? trackletBaseSchemaByFrameIndex[ann.ui.frame_index] === ann.table_info.base_schema
            : false,
      );
      numSameKindInSameView = sameKindInSameView_anns ? sameKindInSameView_anns.length : 0;

      const overlap_tracklets = tracklets?.filter(
        (ann) =>
          (ann as Tracklet).data.view_ref.name === viewRef.name &&
          (ann as Tracklet).data.start_timestep <= (tracklet as Tracklet).data.end_timestep &&
          (ann as Tracklet).data.end_timestep >= (tracklet as Tracklet).data.start_timestep,
      );
      overlap = overlap_tracklets ? overlap_tracklets.length > 0 : false;
      if (overlap_tracklets && overlap_tracklets.length > 0)
        overlapTargetId = overlap_tracklets[0].id;
    } else {
      const sameKindInSameView_anns = annsNotTracklets?.filter(
        //NOTE we "miss" interpolated shapes. So we can "insert"
        (ann) => ann.data.view_ref.id === viewRef.id && baseSchema === ann.table_info.base_schema,
      );
      numSameKindInSameView = sameKindInSameView_anns ? sameKindInSameView_anns.length : 0;
      //WARNING : if we allow relinking of a tracklet child (not allowed now)
      //$curentFrameIndex will not be reliable !
      //anyway, we should find a more reliable frame index
      const overlap_tracklets = tracklets?.filter(
        (ann) =>
          (ann as Tracklet).data.view_ref.name === viewRef.name &&
          (ann as Tracklet).data.start_timestep <= $currentFrameIndex &&
          (ann as Tracklet).data.end_timestep >= $currentFrameIndex,
      );
      overlap = overlap_tracklets ? overlap_tracklets.length > 0 : false;
      if (overlap_tracklets && overlap_tracklets.length > 0)
        overlapTargetId = overlap_tracklets[0].id;
    }
    // ! overlap --> Move
    // overlap && numSameKindInSameView === 0 --> Merge -- need to keep target tracklet
    // overlap && numSameKindInSameView > 0 --> Forbidden
    return {
      hard_forbidden: false,
      overlap: overlap ?? false,
      numSameKindInSameView,
      overlapTargetId,
    };
  };

  let entitiesCombo = derived([entities], ([$entities]) => {
    const res: { id: string; name: string; color: string; target: string }[] = [
      { id: "new", name: "New", color: "", target: "" },
    ];
    $entities.forEach((entity) => {
      //check if there is no annotation of same kind & view_id for this entity
      const { hard_forbidden, overlap, numSameKindInSameView, overlapTargetId } =
        entityAllowInfo(entity);
      if (!hard_forbidden) {
        const displayFeat = getDefaultDisplayFeat(entity);
        const prefixText = overlap
          ? numSameKindInSameView === 0
            ? "Merge in "
            : `Forbidden (${numSameKindInSameView} conflict${numSameKindInSameView > 1 ? "s" : ""}) in `
          : "Move in ";
        res.push({
          id: entity.id,
          name: prefixText + (displayFeat ? `${displayFeat} (${entity.id})` : entity.id),
          color: `${$colorScale[1](entity.id)}3a`,
          target: overlapTargetId,
        });
      }
    });
    selectedEntityId = res[0].id;
    return res;
  });

  const handleChange = (e: Event) => {
    const target = e.target as HTMLSelectElement;
    overlapTargetId = target.options[target.selectedIndex].dataset.overlap ?? "";
    selectedEntityId = target.value;
    mustMerge = target.options[target.selectedIndex].label.startsWith("Merge");
  };
</script>

{#if $entitiesCombo.length > 0}
  <div>
    <span>Select parent entity</span>
    <select
      class="w-full py-1 px-2 border rounded focus:outline-none
bg-slate-100 border-slate-300 focus:border-main"
      on:change={handleChange}
    >
      {#each $entitiesCombo as { id, name, color, target }}
        <option
          value={id}
          data-overlap={target}
          style="background: {color};"
          disabled={name.startsWith("Forbidden")}
        >
          {name}
        </option>
      {/each}
    </select>
  </div>
{/if}
