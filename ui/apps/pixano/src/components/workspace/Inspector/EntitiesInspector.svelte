<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { untrack } from "svelte";
  import { Thumbnail } from "$components/workspace/canvas2d";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import { BaseSchema, BBox, Entity, entityHasTracklets, type AnnotationThumbnail } from "$lib/ui";

  import { ToolType } from "$lib/tools";
  import { defineAnnotationThumbnail, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { toggleAnnotationDisplayControl } from "$lib/utils/displayControl";
  import {
    annotations,
    confidenceThreshold,
    entities,
    highlightedEntity,
    itemMetas,
    mediaViews,
    preAnnotationIsActive,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { sortEntities } from "$lib/utils/entityLookupUtils";
  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import EntityCard from "./EntityCard.svelte";
  import EntitiesSection from "./EntitiesSection.svelte";

  let filteredEntities = $state<Entity[]>([]);
  let hasAppliedFilter = $state(false);

  const globalSourceLabel = { name: "All", kind: "global" };

  const currentEntities = $derived.by(() => (Array.isArray(entities.value) ? entities.value : []));
  const visibleEntities = $derived.by(() =>
    hasAppliedFilter ? filteredEntities : currentEntities,
  );
  const allTopEntities = $derived.by(() =>
    currentEntities
      .filter(
        (ent) => !ent.is_conversation && ent.data.parent_id === "" && visibleEntities.includes(ent),
      )
      .sort(sortEntities),
  );
  const countText = $derived.by(() => {
    const unFilteredCount = currentEntities.filter(
      (ent) => !ent.is_conversation && ent.data.parent_id === "",
    ).length;
    const nextTopCount = allTopEntities.length;
    return unFilteredCount !== nextTopCount
      ? `${nextTopCount} / ${unFilteredCount}`
      : `${nextTopCount}`;
  });

  function applyAnnotationsVisibility(): void {
    // This function writes annotation/entity visibility based on filter criteria.
    // Untrack to prevent circular dependency: we write to stores we also read.
    untrack(() => {
      const confidenceLimit = confidenceThreshold.value[0] ?? 0;
      const visibleEntityIds = new Set(visibleEntities.map((ent) => ent.id));

      // for video: show/hide track in Video inspector depending on filter
      const hasTrackChange = currentEntities.some(
        (ent) => entityHasTracklets(ent) && ent.ui.displayControl.hidden !== !visibleEntityIds.has(ent.id),
      );
      if (hasTrackChange) {
        entities.update((current) =>
          current.map((ent) => {
            if (!entityHasTracklets(ent)) return ent;
            const shouldHide = !visibleEntityIds.has(ent.id);
            if (ent.ui.displayControl.hidden !== shouldHide) {
              ent.ui.displayControl.hidden = shouldHide;
            }
            return ent;
          }),
        );
      }

      // show/hide annotations from active filters and confidence threshold
      const currentAnnotations = annotations.value;
      const hasVisibilityChange = currentAnnotations.some((ann) => {
        if (ann.is_type(BaseSchema.Tracklet)) return false;
        try {
          const topEntity = getTopEntity(ann);
          const isEntityVisible = visibleEntityIds.has(topEntity.id);
          const isLowConfidenceBBox =
            confidenceLimit > 0 &&
            ann.is_type(BaseSchema.BBox) &&
            (ann as BBox).data.confidence < confidenceLimit;
          const shouldHide = !isEntityVisible || isLowConfidenceBBox;
          return ann.ui.displayControl.hidden !== shouldHide;
        } catch {
          return false;
        }
      });

      if (!hasVisibilityChange) return;

      annotations.update((anns) =>
        anns.map((ann) => {
          if (ann.is_type(BaseSchema.Tracklet)) return ann;
          try {
            const topEntity = getTopEntity(ann);
            const isEntityVisible = visibleEntityIds.has(topEntity.id);
            const isLowConfidenceBBox =
              confidenceLimit > 0 &&
              ann.is_type(BaseSchema.BBox) &&
              (ann as BBox).data.confidence < confidenceLimit;
            const shouldHide = !isEntityVisible || isLowConfidenceBBox;
            return toggleAnnotationDisplayControl(ann, "hidden", shouldHide);
          } catch {
            // Do nothing: temporary TextSpan can have no top entity.
            return ann;
          }
        }),
      );
    });
  }

  function hasSameEntitySelection(a: Entity[], b: Entity[]): boolean {
    if (a.length !== b.length) return false;
    const ids = new Set(b.map((ent) => ent.id));
    return a.every((ent) => ids.has(ent.id));
  }

  const selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);

  const thumbnailsByEntityId = $derived.by<Record<string, AnnotationThumbnail | null>>(() => {
    const nextThumbnails: Record<string, AnnotationThumbnail | null> = {};

    if (selectedToolType === ToolType.Pan) {
      const focusedEntityId = highlightedEntity.value;
      if (!focusedEntityId) return nextThumbnails;

      const focusedEntity = currentEntities.find((entity) => entity.id === focusedEntityId);
      if (!focusedEntity) return nextThumbnails;

      for (const view of Object.keys(mediaViews.value)) {
        const viewAnnotations =
          focusedEntity.ui.childs?.filter(
            (ann) =>
              (ann.is_type(BaseSchema.BBox) || ann.is_type(BaseSchema.Mask)) &&
              ann.data.view_name === view,
          ) ?? [];
        if (viewAnnotations.length === 0) continue;

        const annotationOnCurrentFrame = viewAnnotations.find(
          (ann) => ann.ui.frame_index === currentFrameIndex.value,
        );
        const preferredBox =
          annotationOnCurrentFrame ||
          viewAnnotations.find((ann) => ann.is_type(BaseSchema.BBox)) ||
          viewAnnotations[Math.floor(viewAnnotations.length / 2)];
        if (!preferredBox) continue;

        const selectedThumbnail = defineAnnotationThumbnail(itemMetas.value, mediaViews.value, preferredBox);
        if (selectedThumbnail) {
          nextThumbnails[focusedEntityId] = selectedThumbnail;
          break;
        }
      }

      return nextThumbnails;
    }

    const highlightedBoxes = annotations.value.filter(
      (ann) =>
        ann.ui.displayControl.highlighted === "self" &&
        (ann.is_type(BaseSchema.BBox) || ann.is_type(BaseSchema.Mask)),
    );

    if (highlightedBoxes.length === 0) return nextThumbnails;

    const highlightedBoxesByEntityId = Object.groupBy(highlightedBoxes, (ann) => getTopEntity(ann).id);
    for (const [entityId, entityBoxes] of Object.entries(highlightedBoxesByEntityId)) {
      if (!entityBoxes) continue;
      const preferredBox =
        entityBoxes.find((ann) => ann.is_type(BaseSchema.BBox)) ||
        entityBoxes[Math.floor(entityBoxes.length / 2)];
      if (!preferredBox) continue;
      const selectedThumbnail = defineAnnotationThumbnail(itemMetas.value, mediaViews.value, preferredBox);
      if (selectedThumbnail) {
        nextThumbnails[entityId] = selectedThumbnail;
      }
    }

    return nextThumbnails;
  });
  const selectedEntitiesId = $derived.by(() => Object.keys(thumbnailsByEntityId));

  function handleFilter(filteredEnts: Entity[]): void {
    const shouldApplyFilter = !hasSameEntitySelection(filteredEnts, currentEntities);
    if (hasAppliedFilter === shouldApplyFilter && hasSameEntitySelection(filteredEnts, filteredEntities)) {
      return;
    }
    hasAppliedFilter = shouldApplyFilter;
    filteredEntities = filteredEnts;
    applyAnnotationsVisibility();
  }

  function handleConfidenceThresholdChange(): void {
    applyAnnotationsVisibility();
  }

  $effect(() => {
    const confidenceLimit = confidenceThreshold.value[0] ?? 0;
    if (hasAppliedFilter || confidenceLimit > 0) {
      applyAnnotationsVisibility();
    }
  });
</script>

<div class="flex flex-col h-full bg-card overflow-hidden">
  <div class="shrink-0 p-3 pb-0 space-y-4">
    <PreAnnotation />

    {#if !preAnnotationIsActive.value}
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
              {#if thumbnailsByEntityId[selectedEntity]}
                {@const selectedThumbnail = thumbnailsByEntityId[selectedEntity]}
                {#key selectedThumbnail.coords?.[0]}
                  <div class="animate-in fade-in zoom-in-95 duration-300">
                    <Thumbnail
                      imageDimension={selectedThumbnail.baseImageDimensions}
                      coords={selectedThumbnail.coords}
                      imageUrl={`/${selectedThumbnail.uri}`}
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
      {#if !preAnnotationIsActive.value}
        <EntitiesSection
          sourceLabel={globalSourceLabel}
          {countText}
          onFilter={handleFilter}
          onConfidenceThresholdChange={handleConfidenceThresholdChange}
        >
          <div class="space-y-2 mt-2">
            {#each allTopEntities as entity (entity.id)}
              <EntityCard {entity} />
            {/each}
          </div>
        </EntitiesSection>
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
