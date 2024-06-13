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
  import { Eye, EyeOff } from "lucide-svelte";

  import { IconButton } from "@pixano/core/src";

  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { EXISTING_SOURCE_IDS, GROUND_TRUTH } from "../../lib/constants";
  import { itemObjects } from "../../lib/stores/datasetItemWorkspaceStores";

  export let sectionTitle: string;
  export let modelName: string;
  export let numberOfItem: number;

  let visibilityStatus: "hidden" | "shown" | "mixed" = "shown";
  $: tooltipContent =
    visibilityStatus === "hidden" ? `Show ${modelName} objects` : `Hide ${modelName} objects`;

  itemObjects.subscribe((items) => {
    if (!items.length) return;
    const allObjectsOfCurrentModel = items.filter((item) => item.source_id === modelName);
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

  $: itemObjects.update((objects) => {
    return objects.map((object) => {
      const isHidden = visibilityStatus === "hidden";
      if (modelName === GROUND_TRUTH) {
        if (object.source_id === modelName) {
          return toggleObjectDisplayControl(object, "hidden", ["bbox", "mask"], isHidden);
        } else {
          return object;
        }
      }
      if (!EXISTING_SOURCE_IDS.includes(object.source_id)) {
        if (object.source_id === modelName) {
          return toggleObjectDisplayControl(object, "hidden", ["bbox", "mask"], isHidden);
        } else {
          return toggleObjectDisplayControl(object, "hidden", ["bbox", "mask"], true);
        }
      }
      return object;
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

<section class="h-full pb-10">
  <div class="flex items-center justify-between text-slate-800">
    <div class="flex items-center gap-3 w-full">
      <IconButton {tooltipContent} on:click={handleVisibilityIconClick}>
        {#if visibilityStatus === "hidden"}
          <EyeOff class="h-4" />
        {:else}
          <Eye class="h-4" />
        {/if}
      </IconButton>
      <h3 class="uppercase font-medium grow">{sectionTitle}</h3>
      <slot name="modelSelection" />
      <p>{numberOfItem}</p>
    </div>
  </div>
  <div class="p-2 pt-0 max-h-full overflow-y-auto">
    <slot />
  </div>
</section>
