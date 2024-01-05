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
  import { Eye, EyeOff, ChevronRight } from "lucide-svelte";

  import { cn, IconButton } from "@pixano/core/src";

  import { itemObjects } from "../../lib/stores/imageWorkspaceStores";
  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { GROUND_TRUTH, MODEL_RUN } from "../../lib/constants";

  export let sectionTitle: string;
  export let modelName: string;
  let hideAllObjects: boolean | undefined;

  let tooltipContent: string = hideAllObjects ? "show all" : "hide all";
  let open: boolean = true;

  itemObjects.subscribe((items) => {
    const allItemsOfCurrentModelAreHidden = items
      .filter((item) => {
        if (modelName === MODEL_RUN) {
          return item.source_id !== GROUND_TRUTH;
        }
        return item.source_id === modelName;
      })
      .every((item) => item.displayControl?.hidden);
    hideAllObjects = allItemsOfCurrentModelAreHidden;
  });

  $: itemObjects.update((items) => {
    return items.map((item) => {
      if (item.source_id === modelName) {
        return toggleObjectDisplayControl(item, "hidden", ["bbox", "mask"], !!hideAllObjects);
      }
      if (modelName === MODEL_RUN && item.source_id !== GROUND_TRUTH) {
        return toggleObjectDisplayControl(item, "hidden", ["bbox", "mask"], !!hideAllObjects);
      }
      return item;
    });
  });

  const handleVisibilityIconClick = () => {
    hideAllObjects = !hideAllObjects;
  };
</script>

<div class="flex items-center gap-3 justify-between">
  <div class="flex items-center gap-3">
    <IconButton {tooltipContent} on:click={handleVisibilityIconClick}>
      {#if hideAllObjects}
        <EyeOff class="h-4" />
      {:else}
        <Eye class="h-4" />
      {/if}
    </IconButton>
    <h3 class="uppercase font-extralight">{sectionTitle}</h3>
  </div>
  <IconButton on:click={() => (open = !open)}
    ><ChevronRight class={cn("transition", { "rotate-90": open })} /></IconButton
  >
</div>

<div class={cn("p-2", { hidden: !open })}>
  <slot />
</div>
