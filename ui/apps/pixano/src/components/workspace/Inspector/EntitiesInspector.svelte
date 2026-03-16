<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { Thumbnail } from "$components/workspace/canvas2d";
  import { untrack } from "svelte";

  import PreAnnotation from "../PreAnnotation/PreAnnotation.svelte";
  import EntitiesSection from "./EntitiesSection.svelte";
  import EntityCard from "./EntityCard.svelte";
  import {
    buildSearchQueryChips,
    buildTopEntityIdByEntityId,
    buildTopEntitySearchIndex,
    isSearchQueryEmpty,
    matchesParsedSearchQuery,
    parseSearchQuery,
  } from "./entitySearch";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import {
    annotations,
    confidenceThreshold,
    entities,
    entityFilters,
    highlightedEntity,
    itemMetas,
    mediaViews,
    preAnnotationIsActive,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";
  import { ToolType } from "$lib/tools";
  import { BaseSchema, BBox, Entity, entityHasTracklets, type AnnotationThumbnail } from "$lib/ui";
  import { toggleAnnotationDisplayControl } from "$lib/utils/displayControl";
  import {
    defineAnnotationThumbnail,
    getTopEntity,
    sortEntities,
  } from "$lib/utils/entityLookupUtils";

  let filteredEntities = $state<Entity[]>([]);
  let hasAppliedAdvancedFilter = $state(false);
  let searchQuery = $state("");
  let wasVisibilityFilterActive = $state(false);

  const globalSourceLabel = { name: "All", kind: "global" };

  const parsedSearchQuery = $derived.by(() => parseSearchQuery(searchQuery));
  const hasSearchQuery = $derived.by(() => !isSearchQueryEmpty(parsedSearchQuery));
  const searchQueryChips = $derived.by(() => buildSearchQueryChips(parsedSearchQuery));
  const currentEntities = $derived.by(() => (Array.isArray(entities.value) ? entities.value : []));
  const topEntityIdByEntityId = $derived.by(() => buildTopEntityIdByEntityId(currentEntities));
  const topEntities = $derived.by(() =>
    currentEntities
      .filter((ent) => !ent.is_conversation && ent.data.parent_id === "")
      .sort(sortEntities),
  );
  const allTopEntityIds = $derived.by(() => new Set(topEntities.map((ent) => ent.id)));
  const advancedFilteredTopEntityIds = $derived.by(() => {
    if (!hasAppliedAdvancedFilter) return new Set(allTopEntityIds);
    const nextTopEntityIds = new Set<string>();
    for (const entity of filteredEntities) {
      const topEntityId = topEntityIdByEntityId.get(entity.id);
      if (topEntityId && allTopEntityIds.has(topEntityId)) {
        nextTopEntityIds.add(topEntityId);
      }
    }
    return nextTopEntityIds;
  });
  const topEntitySearchIndex = $derived.by(() =>
    buildTopEntitySearchIndex(currentEntities, topEntityIdByEntityId),
  );
  const searchMatchedTopEntityIds = $derived.by(() => {
    if (!hasSearchQuery) return new Set(allTopEntityIds);
    const nextTopEntityIds = new Set<string>();
    for (const topEntityId of allTopEntityIds) {
      const searchCorpus = topEntitySearchIndex.corpusByTopEntityId.get(topEntityId) ?? "";
      const fieldValues =
        topEntitySearchIndex.fieldValuesByTopEntityId.get(topEntityId) ?? new Map();
      if (matchesParsedSearchQuery(searchCorpus, fieldValues, parsedSearchQuery)) {
        nextTopEntityIds.add(topEntityId);
      }
    }
    return nextTopEntityIds;
  });
  const visibleTopEntityIds = $derived.by(() => {
    const nextTopEntityIds = new Set<string>();
    for (const topEntityId of advancedFilteredTopEntityIds) {
      if (searchMatchedTopEntityIds.has(topEntityId)) {
        nextTopEntityIds.add(topEntityId);
      }
    }
    return nextTopEntityIds;
  });
  const visibleEntities = $derived.by(() =>
    currentEntities.filter((entity) => {
      const topEntityId = topEntityIdByEntityId.get(entity.id);
      return topEntityId !== undefined && visibleTopEntityIds.has(topEntityId);
    }),
  );
  const allTopEntities = $derived.by(() =>
    topEntities.filter((ent) => visibleTopEntityIds.has(ent.id)),
  );
  const visibleTopEntityIdsSignature = $derived.by(() =>
    Array.from(visibleTopEntityIds).sort().join("|"),
  );
  const countText = $derived.by(() => {
    const unFilteredCount = topEntities.length;
    const nextTopCount = allTopEntities.length;
    return unFilteredCount !== nextTopCount
      ? `${nextTopCount} / ${unFilteredCount}`
      : `${nextTopCount}`;
  });

  const activeFilters = $derived.by(() => {
    const nextActiveFilters: string[] = [];
    if (hasSearchQuery) {
      nextActiveFilters.push(...searchQueryChips);
    }
    if (hasAppliedAdvancedFilter) {
      const ruleCount = entityFilters.value.length;
      nextActiveFilters.push(ruleCount > 0 ? `Rule Builder (${ruleCount})` : "Rule Builder");
    }
    const confidenceLimit = confidenceThreshold.value[0] ?? 0;
    if (confidenceLimit > 0) {
      nextActiveFilters.push(`Confidence >= ${confidenceLimit.toFixed(2)}`);
    }
    return nextActiveFilters;
  });

  function applyAnnotationsVisibility(): void {
    // This function writes annotation/entity visibility based on filter criteria.
    // Untrack to prevent circular dependency: we write to stores we also read.
    untrack(() => {
      const confidenceLimit = confidenceThreshold.value[0] ?? 0;
      const visibleEntityIds = new Set(visibleEntities.map((ent) => ent.id));
      const visibleTopIds = visibleTopEntityIds;

      // for video: show/hide track in Video inspector depending on filter
      const hasTrackChange = currentEntities.some(
        (ent) =>
          entityHasTracklets(ent) && ent.ui.displayControl.hidden !== !visibleEntityIds.has(ent.id),
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
          const isEntityVisible = visibleTopIds.has(topEntity.id);
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
            const isEntityVisible = visibleTopIds.has(topEntity.id);
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

        const selectedThumbnail = defineAnnotationThumbnail(
          itemMetas.value,
          mediaViews.value,
          preferredBox,
        );
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

    const highlightedBoxesByEntityId = Object.groupBy(
      highlightedBoxes,
      (ann) => getTopEntity(ann).id,
    );
    for (const [entityId, entityBoxes] of Object.entries(highlightedBoxesByEntityId)) {
      if (!entityBoxes) continue;
      const preferredBox =
        entityBoxes.find((ann) => ann.is_type(BaseSchema.BBox)) ||
        entityBoxes[Math.floor(entityBoxes.length / 2)];
      if (!preferredBox) continue;
      const selectedThumbnail = defineAnnotationThumbnail(
        itemMetas.value,
        mediaViews.value,
        preferredBox,
      );
      if (selectedThumbnail) {
        nextThumbnails[entityId] = selectedThumbnail;
      }
    }

    return nextThumbnails;
  });
  const selectedEntitiesId = $derived.by(() => Object.keys(thumbnailsByEntityId));
  const selectedPreviewEntityId = $derived.by(() => selectedEntitiesId[0] ?? null);

  function handleFilter(filteredEnts: Entity[]): void {
    const shouldApplyFilter = !hasSameEntitySelection(filteredEnts, currentEntities);
    if (
      hasAppliedAdvancedFilter === shouldApplyFilter &&
      hasSameEntitySelection(filteredEnts, filteredEntities)
    ) {
      return;
    }
    hasAppliedAdvancedFilter = shouldApplyFilter;
    filteredEntities = filteredEnts;
    applyAnnotationsVisibility();
  }

  function handleSearchQueryChange(value: string): void {
    if (searchQuery === value) return;
    searchQuery = value;
  }

  function handleClearSearch(): void {
    if (!searchQuery) return;
    searchQuery = "";
  }

  function handleConfidenceThresholdChange(): void {
    applyAnnotationsVisibility();
  }

  $effect(() => {
    void visibleTopEntityIdsSignature;
    const confidenceLimit = confidenceThreshold.value[0] ?? 0;
    const hasVisibilityFilterActive =
      hasAppliedAdvancedFilter || hasSearchQuery || confidenceLimit > 0;
    if (hasVisibilityFilterActive || wasVisibilityFilterActive) {
      applyAnnotationsVisibility();
    }
    wasVisibilityFilterActive = hasVisibilityFilterActive;
  });
</script>

<div class="flex flex-col h-full bg-card overflow-hidden">
  <div class="shrink-0 p-3 pb-2 space-y-3 border-b border-border/40 bg-card/95">
    <PreAnnotation />

    <!-- Preview Area -->
    <div>
      <div
        class="group relative flex h-[228px] items-center justify-center overflow-hidden rounded-xl border border-border/50 bg-muted/20 shadow-inner transition-all duration-300 hover:border-primary/20"
      >
        {#if selectedPreviewEntityId && thumbnailsByEntityId[selectedPreviewEntityId]}
          {@const selectedThumbnail = thumbnailsByEntityId[selectedPreviewEntityId]}
          {#key selectedThumbnail.coords?.[0]}
            <div class="animate-in fade-in zoom-in-95 duration-300">
              <Thumbnail
                imageDimension={selectedThumbnail.baseImageDimensions}
                coords={selectedThumbnail.coords}
                imageUrl={`/${selectedThumbnail.uri}`}
                minSide={180}
                maxHeight={200}
                maxWidth={300}
              />
            </div>
          {/key}
        {:else}
          <div class="flex flex-col items-center gap-2 text-center px-8">
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
              Select an entity to lock its preview here
            </p>
          </div>
        {/if}
      </div>
    </div>
  </div>

  <div class="flex-1 min-h-0 overflow-hidden p-3 pt-2">
    <EntitiesSection
      sourceLabel={globalSourceLabel}
      {countText}
      {searchQuery}
      onSearchQueryChange={handleSearchQueryChange}
      onClearSearch={handleClearSearch}
      {activeFilters}
      onFilter={handleFilter}
      onConfidenceThresholdChange={handleConfidenceThresholdChange}
    >
      {#if preAnnotationIsActive.value}
        <div
          class="rounded-xl border border-border/50 bg-muted/30 p-4 text-center text-sm text-muted-foreground"
        >
          Entity exploration is temporarily unavailable while pre-annotation is active.
        </div>
      {:else if allTopEntities.length === 0}
        <div class="rounded-xl border border-border/50 bg-muted/30 p-4 text-center space-y-1">
          <p class="text-sm font-medium">No entities match the current query</p>
          <p class="text-xs text-muted-foreground">
            Adjust search text, confidence threshold, or advanced rules.
          </p>
        </div>
      {:else}
        <div class="space-y-2">
          {#each allTopEntities as entity (entity.id)}
            <EntityCard {entity} />
          {/each}
        </div>
      {/if}
    </EntitiesSection>
  </div>
</div>
