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
  import { ChevronRight, Eye, EyeOff } from "lucide-svelte";

  import { cn, IconButton } from "@pixano/core/src";

  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { GROUND_TRUTH, MODEL_RUN } from "../../lib/constants";
  import { itemObjects } from "../../lib/stores/imageWorkspaceStores";

  export let sectionTitle: string;
  export let modelName: string;

  let visibilityStatus: "hidden" | "shown" | "mixed" = "shown";
  $: tooltipContent = visibilityStatus === "hidden" ? "show all" : "hide all";
  let open: boolean = true;

  itemObjects.subscribe((items) => {
    if (!items.length) return;
    const allObjectsOfCurrentModel = items.filter((item) => {
      if (modelName === MODEL_RUN) {
        return item.source_id !== GROUND_TRUTH;
      }
      return item.source_id === modelName;
    });
    const allObjectsOfCurrentModelAreHidden = allObjectsOfCurrentModel.every(
      (item) => item.displayControl?.hidden,
    );
    if (allObjectsOfCurrentModelAreHidden) {
      visibilityStatus = "hidden";
    }
    const allObjectsOfCurrentModelAreShown = allObjectsOfCurrentModel.every(
      (item) => !item.displayControl?.hidden,
    );
    if (allObjectsOfCurrentModelAreShown) {
      visibilityStatus = "shown";
    }
  });

  $: itemObjects.update((items) => {
    return items.map((item) => {
      if (item.source_id === modelName) {
        if (visibilityStatus === "mixed") return item;
        return toggleObjectDisplayControl(
          item,
          "hidden",
          ["bbox", "mask"],
          visibilityStatus === "hidden",
        );
      }
      if (modelName === MODEL_RUN && item.source_id !== GROUND_TRUTH) {
        if (visibilityStatus === "mixed") return item;
        return toggleObjectDisplayControl(
          item,
          "hidden",
          ["bbox", "mask"],
          visibilityStatus === "hidden",
        );
      }
      return item;
    });
  });

  const handleVisibilityIconClick = () => {
    if (visibilityStatus === "hidden") {
      visibilityStatus = "shown";
    } else if (visibilityStatus === "shown") {
      visibilityStatus = "hidden";
    } else {
      visibilityStatus = "hidden";
    }
  };
</script>

<div class="flex items-center gap-3 justify-between text-slate-800">
  <div class="flex items-center gap-3">
    <IconButton {tooltipContent} on:click={handleVisibilityIconClick}>
      {#if visibilityStatus === "hidden"}
        <EyeOff class="h-4" />
      {:else}
        <Eye class="h-4" />
      {/if}
    </IconButton>
    <h3 class="uppercase font-light">{sectionTitle}</h3>
  </div>
  <IconButton on:click={() => (open = !open)}
    ><ChevronRight class={cn("transition", { "rotate-90": open })} /></IconButton
  >
</div>

<div class={cn("p-2", { hidden: !open })}>
  <slot />
</div>
