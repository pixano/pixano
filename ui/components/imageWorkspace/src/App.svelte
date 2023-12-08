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

  import type { DatasetItem, BBox, Mask, SelectionTool } from "@pixano/core";

  import Toolbar from "./components/Toolbar.svelte";
  import ImageCanvas from "./components/ImageCanvas.svelte";
  import ActionsTabs from "./components/ActionsTabs/ActionsTabs.svelte";
  import { itemObjects, itemBboxes, itemMasks } from "./lib/stores/stores";
  import "./index.css";

  let selectedTool: SelectionTool;
  export let selectedItem: DatasetItem;
  export let masks: Mask[] = [];

  let allBBoxes: BBox[] = [];
  let allMasks: Mask[] = [];

  $: itemBboxes.subscribe((boxes) => (allBBoxes = boxes));
  $: itemMasks.subscribe((masks) => (allMasks = masks));
  $: console.log({ masks, selectedItem, allBBoxes });

  $: itemObjects.set(Object.values(selectedItem.objects).flat());
</script>

<div class="flex w-full pt-[81px] h-full">
  <Toolbar bind:selectedTool />
  <ImageCanvas {selectedTool} {selectedItem} bind:bboxes={allBBoxes} bind:masks={allMasks} />
  <ActionsTabs />
</div>
