<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Slider } from "bits-ui";
  import {
    CircleNotch,
    MagnifyingGlassMinus,
    MagnifyingGlassPlus,
    PushPinSlash,
  } from "phosphor-svelte";

  import EntityTimelineRow from "./EntityTimelineRow.svelte";
  import TimelineFocusEmptyState from "./TimelineFocusEmptyState.svelte";
  import TimelineHeaderSurface from "./TimelineHeaderSurface.svelte";
  import TrackingTimelineRow from "./TrackingTimelineRow.svelte";
  import VideoControls from "./VideoControls.svelte";
  import {
    clearPinnedTimelineEntities,
    pinnedTimelineEntityIds,
    timelineFocusEntityIds,
    togglePinnedTimelineEntity,
  } from "$lib/stores/timelineInspectorStore.svelte";
  import { isTracking } from "$lib/stores/trackingStore.svelte";
  import {
    currentFrameIndex,
    lastFrameIndex,
    playbackState,
    timelineZoom,
  } from "$lib/stores/videoStores.svelte";
  import { entities, mediaViews, selectedTool } from "$lib/stores/workspaceStores.svelte";
  import { panTool, ToolType } from "$lib/tools";
  import { entityHasTracklets, type Entity } from "$lib/ui";
  import { sortEntities } from "$lib/utils/entityLookupUtils";
  import { clearHighlighting } from "$lib/utils/highlightOperations";
  import { updateView } from "$lib/utils/videoOperations";
  import { getCurrentImageTime } from "$lib/utils/videoUtils";

  let videoEntities: Entity[] = $derived.by(() =>
    entities.value
      .filter((entity) => entityHasTracklets(entity) && !entity.ui.displayControl.hidden)
      .sort(sortEntities),
  );
  let entitiesById = $derived.by(() => new Map(videoEntities.map((entity) => [entity.id, entity])));
  let focusedTimelineEntities = $derived.by(() => {
    const focusedEntityId = timelineFocusEntityIds.value[0] ?? null;
    const orderedIds = [
      ...(focusedEntityId ? [focusedEntityId] : []),
      ...timelineFocusEntityIds.value.slice(focusedEntityId ? 1 : 0),
    ];

    return orderedIds
      .map((entityId) => entitiesById.get(entityId))
      .filter((entity): entity is Entity => Boolean(entity));
  });
  const selectedToolType = $derived(selectedTool.value?.type ?? ToolType.Pan);
  const currentTimeLabel = $derived(
    getCurrentImageTime(currentFrameIndex.value, playbackState.value.videoSpeed),
  );
  const totalFrameCount = $derived((lastFrameIndex.value ?? 0) + 1);
  const playheadLeft = $derived((currentFrameIndex.value / Math.max(totalFrameCount - 1, 1)) * 100);

  const resetHighlight = () => {
    if (![ToolType.Pan, ToolType.Fusion].includes(selectedToolType)) {
      clearHighlighting();
    }
  };

  const resetTool = () => {
    if (![ToolType.Pan, ToolType.Fusion].includes(selectedToolType)) {
      selectedTool.value = panTool;
    }
  };

  const onFrameClick = (index: number) => {
    if (currentFrameIndex.value !== index) {
      currentFrameIndex.value = index;
      updateView(currentFrameIndex.value);
    }
  };
</script>

{#if playbackState.value.isLoaded}
  <div class="relative flex h-full flex-col overflow-hidden bg-card">
    <div class="sticky top-0 z-30 border-b border-border/40 bg-card/95 backdrop-blur-sm">
      <div class="flex items-center justify-between gap-3 px-3 py-2">
        <div class="flex min-w-0 items-center gap-2">
          <VideoControls {resetHighlight} />
          <div
            class="flex items-center gap-1.5 rounded-md border border-border/40 bg-background/70 px-2 py-1 text-[11px] text-foreground"
          >
            <span class="font-medium tabular-nums">#{currentFrameIndex.value}</span>
            <span class="text-border">/</span>
            <span class="tabular-nums text-muted-foreground">{totalFrameCount - 1}</span>
          </div>
          <div
            class="rounded-md border border-border/40 bg-background/70 px-2 py-1 text-[11px] tabular-nums text-muted-foreground"
          >
            {currentTimeLabel}
          </div>
          {#if playbackState.value.isBuffering}
            <div
              class="inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-700 dark:text-amber-300"
            >
              <CircleNotch class="h-3 w-3 animate-spin" />
              Buffering
            </div>
          {/if}
        </div>

        <div class="flex items-center gap-2">
          {#if pinnedTimelineEntityIds.value.length > 0}
            <button
              type="button"
              class="inline-flex h-7 items-center gap-1.5 rounded-md border border-border/40 bg-background/70 px-2 text-[11px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
              onclick={clearPinnedTimelineEntities}
              title="Clear pinned timeline entities"
            >
              <PushPinSlash class="h-3.5 w-3.5" />
              {pinnedTimelineEntityIds.value.length}
            </button>
          {/if}
          <div
            class="flex w-[180px] items-center gap-2 rounded-md border border-border/40 bg-background/70 px-2 py-1.5"
          >
            <MagnifyingGlassMinus class="h-3.5 w-3.5 text-muted-foreground" />
            <Slider.Root
              type="multiple"
              bind:value={timelineZoom.value}
              min={100}
              max={Math.max((lastFrameIndex.value ?? 0) * 3, 200)}
              class="relative flex w-full touch-none select-none items-center"
            >
              <span class="relative h-1.5 w-full grow overflow-hidden rounded-full bg-secondary/80">
                <Slider.Range class="absolute h-full bg-primary" />
              </span>
              <Slider.Thumb
                index={0}
                class="block h-3.5 w-3.5 rounded-full border border-primary bg-background shadow-sm ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </Slider.Root>
            <MagnifyingGlassPlus class="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </div>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-auto px-3 py-2">
      <div
        class="relative flex min-h-full flex-col gap-1.5"
        style={`width: ${timelineZoom.value[0]}%`}
      >
        <div
          class="pointer-events-none absolute inset-y-0 z-20 -translate-x-1/2"
          style={`left: ${playheadLeft}%`}
        >
          <div class="absolute left-1/2 top-0 flex -translate-x-1/2 flex-col items-center">
            <span
              class="h-0 w-0 border-x-[5px] border-t-[7px] border-x-transparent border-t-primary drop-shadow-[0_1px_0_hsl(var(--background))]"
            ></span>
            <span
              class="mt-[1px] h-1 w-[2px] rounded-full bg-primary shadow-[0_0_0_1px_hsl(var(--background)/0.9)]"
            ></span>
            <span class="mt-[2px] h-1 w-[2px] rounded-full bg-primary/85"></span>
          </div>
          <span
            class="absolute left-1/2 top-[8px] h-full w-[1px] -translate-x-1/2 bg-[linear-gradient(180deg,hsl(var(--primary))_0%,hsl(var(--primary)/0.92)_14%,hsl(var(--primary)/0.52)_62%,hsl(var(--primary)/0.22)_100%)] shadow-[0_0_0_1px_hsl(var(--background)/0.92),0_0_12px_hsl(var(--primary)/0.20)]"
          ></span>
        </div>

        <TimelineHeaderSurface entities={videoEntities} {onFrameClick} />

        {#if isTracking.value}
          <div
            class="rounded-md border border-amber-500/25 bg-[linear-gradient(180deg,rgba(245,158,11,0.10)_0%,rgba(245,158,11,0.03)_100%)] px-1.5 py-1.5"
          >
            <TrackingTimelineRow />
          </div>
        {/if}

        <div class="flex flex-col gap-1">
          {#if focusedTimelineEntities.length === 0}
            <TimelineFocusEmptyState />
          {:else}
            {#each focusedTimelineEntities as entity, index (entity.id)}
              <EntityTimelineRow
                {entity}
                views={mediaViews.value}
                {onFrameClick}
                {resetTool}
                isPrimaryFocus={index === 0}
                isPinned={pinnedTimelineEntityIds.value.includes(entity.id)}
                onTogglePin={() => togglePinnedTimelineEntity(entity.id)}
              />
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
