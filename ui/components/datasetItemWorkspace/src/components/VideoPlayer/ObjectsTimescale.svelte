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

  import { ContextMenu, type ItemObject } from "@pixano/core";

  export let videoSpeed: number;
  export let zoomLevel: number[];
  export let object: ItemObject;
  export let videoTotalLengthInMs: number;
  export let lastImageIndex: number;
</script>

<div class="border-b border-slate-200 h-12 p-2 pl-0 w-full grid grid-cols-[25%_1fr]">
  <p class="sticky left-0 z-10 bg-white pl-2">{object.id}</p>
  <div class="w-full flex gap-5 relative" style={`width: ${zoomLevel[0]}%`}>
    {#if object.bbox && object.bbox.coordinates}
      {#each object.bbox.coordinates as bbox}
        <ContextMenu.Root>
          <ContextMenu.Trigger
            class="h-full bg-emerald-500 absolute"
            style={`left: ${((bbox.startIndex * videoSpeed) / videoTotalLengthInMs) * 100}%; width: ${((((bbox.endIndex > lastImageIndex ? lastImageIndex : bbox.endIndex) - bbox.startIndex) * videoSpeed) / videoTotalLengthInMs) * 100}%`}
          >
            <p on:contextmenu|preventDefault={(e) => console.log(e)} class="h-full w-full" />
            <span
              class="w-4 h-4 block bg-indigo-500 rounded-full absolute left-[-0.5rem] top-1/2 translate-y-[-50%]"
            />
            <span
              class="w-4 h-4 block bg-orange-500 rounded-full absolute right-[-0.5rem] top-1/2 translate-y-[-50%]"
            />
          </ContextMenu.Trigger>
          <ContextMenu.Content class="w-64">
            <ContextMenu.Item inset>Add a point</ContextMenu.Item>
            <ContextMenu.Item inset>Remove point</ContextMenu.Item>
            <ContextMenu.Item inset>Edit point</ContextMenu.Item>
          </ContextMenu.Content>
        </ContextMenu.Root>
      {/each}
    {/if}
  </div>
</div>
