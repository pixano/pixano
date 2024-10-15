<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { annotations, tracks, views } from "../../lib/stores/datasetItemWorkspaceStores";

  import ObjectTrack from "./ObjectTrack.svelte";
  import TimeTrack from "./TimeTrack.svelte";
  import VideoPlayerRow from "./VideoPlayerRow.svelte";
  import VideoControls from "./VideoControls.svelte";

  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { SliderRoot } from "@pixano/core";
  import { onMount } from "svelte";

  export let updateView: (frameIndex: number) => void;

  onMount(() => {
    updateView($currentFrameIndex);
    videoControls.update((old) => ({ ...old, isLoaded: true }));
  });

  const onTimeTrackClick = (index: number) => {
    currentFrameIndex.set(index);
    updateView($currentFrameIndex);
  };

  annotations.subscribe((value) => {
    const highlightedObject = value.find((item) => item.highlighted === "self");
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
        <TimeTrack slot="timeTrack" {updateView} />
      </VideoPlayerRow>
    </div>
    <div class="flex flex-col grow z-10">
      {#each Object.values($tracks) as track}
        <VideoPlayerRow>
          <ObjectTrack slot="timeTrack" {track} views={$views} {onTimeTrackClick} {updateView} />
        </VideoPlayerRow>
      {/each}
    </div>
    <div class="px-2 sticky bottom-0 left-0 z-20 bg-white shadow flex justify-between">
      <VideoControls {updateView} />
      <SliderRoot
        class="max-w-[200px]"
        bind:value={$videoControls.zoomLevel}
        min={100}
        max={Math.max($lastFrameIndex * 3, 200)}
      />
    </div>
  </div>
{/if}
