<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { Thumbnail } from "@pixano/canvas2d";
  import { BaseSchema, BBox, Entity, Source, type ObjectThumbnail } from "@pixano/core";

  import {
    defineObjectThumbnail,
    getTopEntity,
    toggleObjectDisplayControl,
  } from "../../lib/api/objectsApi";
  import {
    annotations,
    confidenceThreshold,
    entities,
    itemMetas,
    mediaViews,
    preAnnotationIsActive,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { sortEntities } from "../../lib/utils/sortEntities";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import ObjectCard from "./ObjectCard.svelte";
  import ObjectsSection from "./ObjectsSection.svelte";

  let selectedEntitiesId: string[];
  let allTopEntities: Entity[];
  let filteredEntities: Entity[] = $entities;
  let countText: string;
  const thumbnails: Record<string, ObjectThumbnail | null> = {};

  //Note: Previously Entities where grouped by source
  //Now they're all displayed regardless of source
  //so we fake a global source for ObjectsSection (may be rewritten later)
  const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
  const globalSource = new Source({
    id: "pixano_source",
    created_at: now,
    updated_at: now,
    table_info: { name: "source", group: "source", base_schema: BaseSchema.Source },
    data: { name: "All", kind: "Global", metadata: {} },
  });

  $: if ($entities || filteredEntities) updateObjectsEntities();
  const updateObjectsEntities = () => {
    //for video: show/hide track in Video inspector depending on filter
    $entities.forEach((ent) => {
      if (ent.is_track) ent.ui.displayControl.hidden = !filteredEntities.includes(ent);
    });

    //show shapes of entities in filter, hide others
    annotations.update((anns) =>
      anns.map((ann) => {
        if (!ann.is_type(BaseSchema.Tracklet))
          toggleObjectDisplayControl(ann, "hidden", !filteredEntities.includes(getTopEntity(ann)));
        return ann;
      }),
    );

    //rebuild list of ObjectInspector
    allTopEntities = $entities
      .filter(
        (ent) =>
          !ent.is_conversation && ent.data.parent_ref.id === "" && filteredEntities.includes(ent),
      )
      .sort(sortEntities);

    //update count
    const unFilteredCount = $entities.filter(
      (ent) => !ent.is_conversation && ent.data.parent_ref.id === "",
    ).length;
    if (unFilteredCount !== allTopEntities.length) {
      countText = `${allTopEntities.length} / ${unFilteredCount}`;
    } else {
      countText = `${allTopEntities.length}`;
    }

    //apply current confidence threshold
    handleConfidenceThresholdChange();
  };

  $: if ($annotations) handleSelectedEntitiesBBoxThumbnails();
  const handleSelectedEntitiesBBoxThumbnails = () => {
    //selected entities thumbnails on top of ObjectsInspector
    selectedEntitiesId = [];

    const highlightedBoxes = $annotations.filter(
      (ann) => ann.ui.displayControl.highlighted === "self" && ann.is_type(BaseSchema.BBox),
    );

    if (highlightedBoxes.length > 0) {
      const highlightedBoxesByEntityId = Object.groupBy(
        highlightedBoxes,
        (ann) => getTopEntity(ann).id,
      );
      selectedEntitiesId = Object.keys(highlightedBoxesByEntityId);
      for (const [entityId, entityBoxes] of Object.entries(highlightedBoxesByEntityId)) {
        if (entityBoxes) {
          const selectedBox = entityBoxes[Math.floor(entityBoxes.length / 2)];
          if (selectedBox) {
            const selectedThumbnail = defineObjectThumbnail($itemMetas, $mediaViews, selectedBox);
            if (selectedThumbnail) {
              thumbnails[entityId] = selectedThumbnail;
            }
          }
        }
      }
    }
  };

  const handleFilter = (filteredEnts: Entity[]) => {
    filteredEntities = filteredEnts;
  };

  const handleConfidenceThresholdChange = () => {
    annotations.update((anns) =>
      anns.map((ann) => {
        const topEnt = getTopEntity(ann);
        const hide =
          $confidenceThreshold[0] === 0.0
            ? false
            : (ann as BBox).data.confidence < $confidenceThreshold[0];
        if (allTopEntities.includes(topEnt)) {
          if (ann.is_type(BaseSchema.BBox)) {
            return toggleObjectDisplayControl(ann, "hidden", hide);
          }
        }
        return ann;
      }),
    );
  };
</script>

<div class="p-2 w-full">
  <PreAnnotation />
  {#if !$preAnnotationIsActive}
    {#if selectedEntitiesId.length > 0}
      <span class="flex justify-center font-medium text-slate-800">
        Selected object{selectedEntitiesId.length > 1 ? "s" : ""}
      </span>
      {#each selectedEntitiesId as selectedEntity}
        <span class="flex justify-center text-slate-800">{selectedEntity}</span>
        {#if thumbnails[selectedEntity]}
          {#key thumbnails[selectedEntity].coords[0]}
            <Thumbnail
              imageDimension={thumbnails[selectedEntity].baseImageDimensions}
              coords={thumbnails[selectedEntity].coords}
              imageUrl={`/${thumbnails[selectedEntity].uri}`}
              minSide={150}
              maxHeight={200}
              maxWidth={200}
            />
          {/key}
        {/if}
      {/each}
    {/if}
    <ObjectsSection
      source={globalSource}
      {countText}
      on:filter={(event) => handleFilter(event.detail)}
      on:confidenceThresholdChange={() => handleConfidenceThresholdChange()}
    >
      {#key allTopEntities.length}
        {#each allTopEntities as entity}
          <ObjectCard {entity} />
        {/each}
      {/key}
    </ObjectsSection>
  {/if}
</div>
