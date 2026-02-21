<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { untrack } from "svelte";

  import { Slider } from "bits-ui";
  import { ZoomIn, ZoomOut } from "lucide-svelte";

  import { ToolType, panTool } from "$lib/tools";
  import { BBox, Entity, type KeypointAnnotation } from "$lib/ui";

  import { clearHighlighting } from "$lib/utils/highlightOperations";
  import { updateView } from "$lib/utils/videoOperations";
  import { entities, mediaViews, selectedTool } from "$lib/stores/workspaceStores.svelte";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "$lib/stores/videoStores.svelte";
  import { sortEntities } from "$lib/utils/sortEntities";
  import EntityTrack from "./EntityTrack.svelte";
  import TimeTrack from "./TimeTrack.svelte";
  import VideoControls from "./VideoControls.svelte";
  import VideoPlayerRow from "./VideoPlayerRow.svelte";

  interface Props {
    bboxes: BBox[];
    keypoints: KeypointAnnotation[];
  }

  let { bboxes, keypoints }: Props = $props();

  let tracks: Entity[] = $derived(entities.value.filter((entity) => entity.is_track).sort(sortEntities));

  $effect(() => {
    untrack(() => videoControls.update((old) => ({ ...old, isLoaded: true })));
  });

  const resetHighlight = () => {
    if (![ToolType.Pan, ToolType.Fusion].includes(selectedTool.value.type)) {
      clearHighlighting();
    }
  };

  const resetTool = () => {
    if (![ToolType.Pan, ToolType.Fusion].includes(selectedTool.value.type)) {
      selectedTool.value = panTool;
    }
  };

  const onTimeTrackClick = (index: number) => {
    if (currentFrameIndex.value !== index) {
      currentFrameIndex.value = index;
      updateView(currentFrameIndex.value);
    }
  };
</script>

{#if videoControls.value.isLoaded}
  <div class="h-full bg-card overflow-x-auto relative flex flex-col scroll-smooth">
    <div class="sticky top-0 bg-card z-20">
      <VideoPlayerRow class="bg-card ">
        {#snippet timeTrack()}
                <TimeTrack  {resetTool} {resetHighlight} />
              {/snippet}
      </VideoPlayerRow>
    </div>
    <div class="flex flex-col grow z-10">
      {#each tracks as track (track.id)}
        {#if !track.ui.displayControl.hidden}
          <VideoPlayerRow>
            {#snippet timeTrack()}
                        <EntityTrack
                
                {track}
                views={mediaViews.value}
                {onTimeTrackClick}
                {bboxes}
                {keypoints}
                {resetTool}
              />
                      {/snippet}
          </VideoPlayerRow>
        {/if}
      {/each}
    </div>
    <div class="px-2 sticky bottom-0 left-0 z-20 bg-card shadow flex justify-between">
      <VideoControls {resetHighlight} />
      <div class="relative flex justify-between items-center gap-4 p-4 w-full max-w-[250px]">
        <div title="Zoom out" class="text-primary"><ZoomOut /></div>
        <Slider.Root
          type="multiple"
          bind:value={videoControls.value.zoomLevel}
          min={100}
          max={Math.max(lastFrameIndex.value * 3, 200)}
          class="relative flex w-full touch-none select-none items-center"
        >
          <span class="relative h-2 w-full grow overflow-hidden rounded-full bg-secondary">
            <Slider.Range class="absolute h-full bg-primary" />
          </span>
          <Slider.Thumb
            index={0}
            class="block h-4 w-4 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
          />
        </Slider.Root>
        <div title="Zoom in" class="text-primary"><ZoomIn /></div>
      </div>
    </div>
  </div>
{/if}
