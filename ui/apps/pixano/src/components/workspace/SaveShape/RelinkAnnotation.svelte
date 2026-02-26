<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Annotation, BaseSchema, Entity, Tracklet, type Reference } from "$lib/ui";

  import { getTopEntity } from "$lib/utils/entityLookupUtils";
  import { OVERLAPIDS_SEPARATOR } from "$lib/utils/entityRelink";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";
  import { colorScale, entities } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";

  interface Props {
    selectedEntityId?: string;
    mustMerge?: boolean;
    overlapTargetId?: string;
    baseSchema: BaseSchema;
    viewRef: Reference;
    track?: Annotation | null;
  }

  let {
    selectedEntityId = $bindable("new"),
    mustMerge = $bindable(false),
    overlapTargetId = $bindable(""),
    baseSchema,
    viewRef,
    track = null
  }: Props = $props();

  const entityAllowInfo = (
    entity: Entity,
  ): {
    hard_forbidden: boolean;
    overlap: boolean;
    numSameKindInSameView: number;
    overlapTargetIds: string[];
  } => {
    if (
      entity.data.parent_id !== "" ||
      entity.is_conversation ||
      (track && getTopEntity(track).id === entity.id)
    )
      return {
        hard_forbidden: true,
        overlap: false,
        numSameKindInSameView: 0,
        overlapTargetIds: [],
      };
    const entityTracks = entity.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Tracklet));
    const annsNotTracks = entity.ui.childs?.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
    let numSameKindInSameView: number = 0;
    let overlap: boolean | undefined = undefined;
    let overlapTargetIds: string[] = [];
    if (track && track.is_type(BaseSchema.Tracklet)) {
      const trackBaseSchemaByFrameIndex = (track as Tracklet).ui.childs.reduce(
        (acc, ann) => {
          if (ann.ui.frame_index) {
            acc[ann.ui.frame_index] = ann.table_info.base_schema;
          }
          return acc;
        },
        {} as Record<number, BaseSchema>,
      );
      const sameKindInSameView_anns = annsNotTracks?.filter(
        //NOTE we "miss" interpolated shapes. So we can "insert"
        (ann) =>
          ann.ui.frame_index
            ? ann.data.view_name === viewRef.name &&
              trackBaseSchemaByFrameIndex[ann.ui.frame_index] === ann.table_info.base_schema
            : false,
      );
      numSameKindInSameView = sameKindInSameView_anns ? sameKindInSameView_anns.length : 0;

      const overlap_tracks = entityTracks?.filter(
        (ann) =>
          (ann as Tracklet).data.view_name === viewRef.name &&
          (ann as Tracklet).data.start_frame <= (track as Tracklet).data.end_frame &&
          (ann as Tracklet).data.end_frame >= (track as Tracklet).data.start_frame,
      );
      overlap = overlap_tracks ? overlap_tracks.length > 0 : false;
      if (overlap_tracks && overlap_tracks.length > 0)
        overlapTargetIds = overlap_tracks.map((ann) => ann.id);
    } else {
      const sameKindInSameView_anns = annsNotTracks?.filter(
        //NOTE we "miss" interpolated shapes. So we can "insert"
        (ann) => ann.data.frame_id === viewRef.id && baseSchema === ann.table_info.base_schema,
      );
      numSameKindInSameView = sameKindInSameView_anns ? sameKindInSameView_anns.length : 0;
      //WARNING : if we allow relinking of a tracklet child (not allowed now)
      //$curentFrameIndex will not be reliable !
      //anyway, we should find a more reliable frame index
      const overlap_tracks = entityTracks?.filter(
        (ann) =>
          (ann as Tracklet).data.view_name === viewRef.name &&
          (ann as Tracklet).data.start_frame <= currentFrameIndex.value &&
          (ann as Tracklet).data.end_frame >= currentFrameIndex.value,
      );
      overlap = overlap_tracks ? overlap_tracks.length > 0 : false;
      if (overlap_tracks && overlap_tracks.length > 0)
        overlapTargetIds = overlap_tracks.map((ann) => ann.id);
    }
    // ! overlap --> Move
    // overlap && numSameKindInSameView === 0 --> Merge -- need to keep target tracklet
    // overlap && numSameKindInSameView > 0 --> Forbidden
    return {
      hard_forbidden: false,
      overlap: overlap ?? false,
      numSameKindInSameView,
      overlapTargetIds,
    };
  };

  let entitiesCombo = $derived.by(() => {
    const currentEntities = entities.value;
    const res: { id: string; name: string; color: string; targets: string[] }[] = [
      { id: "new", name: "New", color: "", targets: [] },
    ];
    currentEntities.forEach((entity) => {
      //check if there is no annotation of same kind & view_id for this entity
      const { hard_forbidden, overlap, numSameKindInSameView, overlapTargetIds } =
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
          color: `${colorScale.value[1](entity.id)}3a`,
          targets: overlapTargetIds,
        });
      }
    });
    return res;
  });

  $effect(() => {
    if (entitiesCombo.length > 0) {
      selectedEntityId = entitiesCombo[0].id;
    }
  });

  const handleChange = (e: Event) => {
    const target = e.target as HTMLSelectElement;
    overlapTargetId = target.options[target.selectedIndex].dataset.overlap ?? "";
    selectedEntityId = target.value;
    mustMerge = target.options[target.selectedIndex].label.startsWith("Merge");
  };
</script>

{#if entitiesCombo.length > 0}
  <div>
    <span>Select parent entity</span>
    <select
      class="w-full py-1 px-2 border rounded focus:outline-none
bg-muted border-border focus:border-main"
      onchange={handleChange}
    >
      {#each entitiesCombo as { id, name, color, targets }}
        <option
          value={id}
          data-overlap={targets.join(OVERLAPIDS_SEPARATOR)}
          style="background: {color};"
          disabled={name.startsWith("Forbidden")}
        >
          {name}
        </option>
      {/each}
    </select>
  </div>
{/if}
