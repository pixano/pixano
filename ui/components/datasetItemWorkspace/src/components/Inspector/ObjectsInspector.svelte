<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { afterUpdate } from "svelte";

  import { Thumbnail } from "@pixano/canvas2d";
  import { BaseSchema, Entity, Source, type ObjectThumbnail } from "@pixano/core";

  import { defineObjectThumbnail, getTopEntity } from "../../lib/api/objectsApi";
  import {
    annotations,
    entities,
    itemMetas,
    mediaViews,
    preAnnotationIsActive,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { sortEntites } from "../../lib/utils/sortEntities";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import ObjectCard from "./ObjectCard.svelte";
  import ObjectsModelSection from "./ObjectsModelSection.svelte";

  let allTopEntities: Entity[];
  let selectedEntitiesId: string[];
  const thumbnails: Record<string, ObjectThumbnail | null> = {};

  //Note: Previously Entities where grouped by source
  //Now they're all displayed regardless of source
  //so we fake a global source for ObjectsModelSection (may be rewritten later)
  const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
  const globalSource = new Source({
    id: "pixano_source",
    created_at: now,
    updated_at: now,
    table_info: { name: "source", group: "source", base_schema: BaseSchema.Source },
    data: { name: "All", kind: "Global", metadata: {} },
  });

  let somethingChanged = 0;
  $: $annotations, $entities, handleAnnotationSortedByModel(); // eslint-disable-line @typescript-eslint/no-unused-expressions

  const handleAnnotationSortedByModel = () => {
    //svelte hack: use a temp Set to set the whole list once
    const allTopEntitiesSet = new Set<Entity>();
    $annotations.forEach((ann) => {
      const top_entity = getTopEntity(ann);
      if (!top_entity.is_conversation) allTopEntitiesSet.add(top_entity);
    });
    allTopEntities = Array.from(allTopEntitiesSet).sort(sortEntites);
    selectedEntitiesId = [];

    const highlightedBoxes = $annotations.filter(
      (ann) => ann.ui.highlighted === "self" && ann.is_type(BaseSchema.BBox),
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
    //hack to refresh ObjectInspector every time this function is call
    somethingChanged = (somethingChanged + 1) % 2;
  };

  afterUpdate(() => {
    handleAnnotationSortedByModel();
  });
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
    <ObjectsModelSection source={globalSource} numberOfItem={allTopEntities.length}>
      {#key somethingChanged}
        {#each allTopEntities as entity}
          <ObjectCard {entity} />
        {/each}
      {/key}
    </ObjectsModelSection>
  {/if}
</div>
