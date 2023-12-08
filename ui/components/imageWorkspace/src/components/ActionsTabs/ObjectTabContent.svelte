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
  import { SlidersHorizontal } from "lucide-svelte";
  import Combobox from "@pixano/core/src/lib/components/ui/combobox/combobox.svelte";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import { utils, type ItemObject } from "@pixano/core";

  import ObjectTabFlatItem from "./ObjectTabFlatItem.svelte";
  import ObjectTabLabelItem from "./ObjectTabLabelsItem.svelte";
  import ActionsTabsSearchInput from "./ActionsTabsSearchInput.svelte";
  import { itemObjects, colorRange } from "../../lib/stores/stores";
  import { GROUND_TRUTH } from "../../lib/constants";
  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";

  let value = "flat";
  let allItemObjects: ItemObject[] = [];
  let hideAllGroundTruthObjects = false;

  itemObjects.subscribe((value) => {
    allItemObjects = value;
  });

  $: itemObjects.update((items) => {
    return items.map((item) => {
      if (item.source_id === GROUND_TRUTH) {
        return toggleObjectDisplayControl(
          item,
          "hidden",
          ["bbox", "mask"],
          hideAllGroundTruthObjects,
        );
      }
      return item;
    });
  });

  const handleVisibilityIconClick = () => {
    hideAllGroundTruthObjects = !hideAllGroundTruthObjects;
  };

  let colorRangeValue: string[] = [];
  colorRange.subscribe((value) => (colorRangeValue = value));
  let colorScale = utils.ordinalColorScale(colorRangeValue);
</script>

<div class="p-4">
  <div class="flex justify-between items-center mb-4">
    <div class="flex gap-2">
      <span class="flex items-center">view</span>
      <Combobox
        placeholder="Select a view"
        bind:value
        listItems={[
          { value: "flat", label: "flat" },
          { value: "labels", label: "labels" },
        ]}
      />
    </div>
    <IconButton>
      <SlidersHorizontal class="h-4" />
    </IconButton>
  </div>
  {#if value === "flat"}
    <div>
      <h3 class="uppercase font-extralight">Ground truth</h3>
      <ActionsTabsSearchInput
        on:click={handleVisibilityIconClick}
        bind:hideAllObjects={hideAllGroundTruthObjects}
      />
      {#each allItemObjects as itemObject}
        {#if itemObject.source_id === GROUND_TRUTH}
          <ObjectTabFlatItem bind:itemObject {colorScale} />
        {/if}
      {/each}
      <h3 class="uppercase font-extralight mt-8">Model run</h3>
      <ActionsTabsSearchInput />
    </div>
  {/if}
  {#if value === "labels"}
    <ActionsTabsSearchInput />
    <ObjectTabLabelItem open />
    <ObjectTabLabelItem name="Girl" />
    <ObjectTabLabelItem name="Goat" />
  {/if}
</div>
