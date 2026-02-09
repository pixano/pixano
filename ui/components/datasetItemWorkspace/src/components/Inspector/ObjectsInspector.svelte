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
          try {
            toggleObjectDisplayControl(
              ann,
              "hidden",
              !filteredEntities.includes(getTopEntity(ann)),
            );
          } catch {
            //do nothing -- happen with temporary TextSpan which doesn't have a topEntity.
          }

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
      (ann) =>
        ann.ui.displayControl.highlighted === "self" &&
        (ann.is_type(BaseSchema.BBox) || ann.is_type(BaseSchema.Mask)),
    );

    if (highlightedBoxes.length > 0) {
      const highlightedBoxesByEntityId = Object.groupBy(
        highlightedBoxes,
        (ann) => getTopEntity(ann).id,
      );
      selectedEntitiesId = Object.keys(highlightedBoxesByEntityId);
      for (const [entityId, entityBoxes] of Object.entries(highlightedBoxesByEntityId)) {
        if (entityBoxes) {
          // Prefer BBox if available among highlighted objects for this entity
          const preferredBox =
            entityBoxes.find((ann) => ann.is_type(BaseSchema.BBox)) ||
            entityBoxes[Math.floor(entityBoxes.length / 2)];
          if (preferredBox) {
            const selectedThumbnail = defineObjectThumbnail($itemMetas, $mediaViews, preferredBox);
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

<div class="flex flex-col h-full bg-card overflow-hidden">
  <div class="shrink-0 p-3 pb-0 space-y-4">
    <PreAnnotation />

    {#if !$preAnnotationIsActive}
      <!-- Preview Area -->
      <div class="space-y-2">
        <div class="flex items-center justify-between px-1">
          <h3 class="text-[10px] font-bold uppercase tracking-[0.05em] text-muted-foreground/80">
            Object Preview
          </h3>
        </div>
        <div
          class="group relative flex h-[180px] items-center justify-center overflow-hidden rounded-xl border border-border/50 bg-muted/20 shadow-inner transition-all duration-300 hover:border-primary/20"
        >
          {#if selectedEntitiesId.length > 0}
            {#each selectedEntitiesId as selectedEntity}
              {#if thumbnails[selectedEntity]}
                {#key thumbnails[selectedEntity].coords[0]}
                  <div class="animate-in fade-in zoom-in-95 duration-300">
                    <Thumbnail
                      imageDimension={thumbnails[selectedEntity].baseImageDimensions}
                      coords={thumbnails[selectedEntity].coords}
                      imageUrl={`/${thumbnails[selectedEntity].uri}`}
                      minSide={150}
                      maxHeight={160}
                      maxWidth={240}
                    />
                  </div>
                {/key}
              {/if}
            {/each}
          {:else}
            <div class="flex flex-col items-center gap-2 text-center px-6">
              <div class="w-10 h-10 rounded-full bg-muted/50 flex items-center justify-center mb-1">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="text-muted-foreground/40"
                >
                  <path
                    d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"
                  ></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <circle cx="10" cy="13" r="2"></circle>
                  <path d="m20 17-1.09-1.09a2 2 0 0 0-2.82 0L10 22"></path>
                </svg>
              </div>
              <p class="text-xs font-medium text-muted-foreground/60">
                Select an object to see its preview
              </p>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- Scrollable List Area -->
  <div class="flex-1 overflow-y-auto custom-scrollbar">
    <div class="p-3 pt-2">
      {#if !$preAnnotationIsActive}
        <ObjectsSection
          source={globalSource}
          {countText}
          on:filter={(event) => handleFilter(event.detail)}
          on:confidenceThresholdChange={() => handleConfidenceThresholdChange()}
        >
          <div class="space-y-2 mt-2">
            {#key allTopEntities.length}
              {#each allTopEntities as entity}
                <ObjectCard {entity} />
              {/each}
            {/key}
          </div>
        </ObjectsSection>
      {/if}
    </div>
  </div>
</div>

<style>
  .custom-scrollbar::-webkit-scrollbar {
    width: 4px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: hsl(var(--border));
    border-radius: 10px;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground) / 0.3);
  }
</style>
