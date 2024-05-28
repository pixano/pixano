<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";

  import ObjectTrack from "./ObjectTrack.svelte";
  import TimeTrack from "./TimeTrack.svelte";
  import VideoPlayerRow from "./VideoPlayerRow.svelte";
  import {
    currentFrameIndex,
    lastFrameIndex,
    videoControls,
  } from "../../lib/stores/videoViewerStores";
  import { Thumbnail } from "@pixano/canvas2d";
  import { SliderRoot } from "@pixano/core";

  export let updateView: (frameIndex: number) => void;
  export let imagesDimensions: Record<string, { width: number; height: number }>;
  export let imagesFilesUrls: Record<string, string[]>;

  const onTimeTrackClick = (index: number) => {
    currentFrameIndex.set(index);
    updateView($currentFrameIndex);
  };

  itemObjects.subscribe((value) => {
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
      <div class="grow">
        {#each Object.values($itemObjects) as object}
          {#if object.datasetItemType === "video"}
            <VideoPlayerRow>
              <ObjectTrack slot="timeTrack" {object} {onTimeTrackClick} {updateView}>
                <Thumbnail
                  imageDimension={imagesDimensions[object.view_id]}
                  coords={object.track[0].keyBoxes[0].coords}
                  imageUrl={`/${imagesFilesUrls[object.view_id][object.track[0].start]}`}
                />
              </ObjectTrack>
            </VideoPlayerRow>
          {/if}
        {/each}
      </div>
      <div class="max-w-[200px] p-4 sticky bottom-0 left-0 z-20 bg-white shadow">
        <SliderRoot bind:value={$videoControls.zoomLevel} min={100} max={$lastFrameIndex * 3} />
      </div>
    </div>
  </div>
{/if}
