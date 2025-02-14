<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import { BBox, SliderRoot, Track, type KeypointsTemplate } from "@pixano/core";

  import { panTool } from "../../lib/settings/selectionTools";
  import {
    annotations,
    entities,
    selectedTool,
    views,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import ObjectTrack from "./ObjectTrack.svelte";
  import TimeTrack from "./TimeTrack.svelte";
  import VideoControls from "./VideoControls.svelte";
  import VideoPlayerRow from "./VideoPlayerRow.svelte";

  export let updateView: (frameIndex: number) => void;
  export let bboxes: BBox[];
  export let keypoints: KeypointsTemplate[];

  let tracks: Track[] = [];
  entities.subscribe((entities) => {
    tracks = entities.filter((entity) => entity.is_track);
  });

  onMount(() => {
    videoControls.update((old) => ({ ...old, isLoaded: true }));
  });

  const resetTool = () => {
    if (![ToolType.Pan, ToolType.Fusion].includes($selectedTool.type)) {
      selectedTool.set(panTool);
    }
  };

  const onTimeTrackClick = (index: number) => {
    if ($currentFrameIndex !== index) {
      currentFrameIndex.set(index);
      updateView($currentFrameIndex);
    }
  };

  annotations.subscribe((value) => {
    const highlightedObject = value.find((item) => item.ui.highlighted === "self");
    if (!highlightedObject) return;
    const element = document.querySelector(`#video-object-${highlightedObject.id}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
</script>

{#if $videoControls.isLoaded}
  <div class="h-full bg-white overflow-x-auto relative flex flex-col">
    <div class="sticky top-0 bg-white z-20">
      <VideoPlayerRow class="bg-white ">
        <TimeTrack slot="timeTrack" {updateView} {resetTool} />
      </VideoPlayerRow>
    </div>
    <div class="flex flex-col grow z-10">
      {#each tracks as track (track.ui.childs)}
        {#if !track.ui.hidden}
          <VideoPlayerRow>
            <ObjectTrack
              slot="timeTrack"
              {track}
              views={$views}
              {onTimeTrackClick}
              {bboxes}
              {keypoints}
              {resetTool}
            />
          </VideoPlayerRow>
        {/if}
      {/each}
    </div>
    <div class="px-2 sticky bottom-0 left-0 z-20 bg-white shadow flex justify-between">
      <VideoControls {updateView} {resetTool} />
      <SliderRoot
        class="max-w-[250px]"
        bind:value={$videoControls.zoomLevel}
        min={100}
        max={Math.max($lastFrameIndex * 3, 200)}
      />
    </div>
  </div>
{/if}
