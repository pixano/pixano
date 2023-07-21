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

  // Imports
  import { afterUpdate, createEventDispatcher, onMount } from "svelte";

  import { Canvas2D, tools } from "@pixano/canvas2d";
  import { utils } from "@pixano/core";

  import ExplorationPanel from "./ExplorationPanel.svelte";

  import type { ItemData, Mask, BBox, AnnotationCategory } from "@pixano/core";

  // Exports
  export let selectedItem: ItemData;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;
  export let annotations: Array<AnnotationCategory>;
  export let features = null;

  let panTool = tools.createPanTool();
  let selectedTool: tools.Tool = panTool;

  let categoryColor;

  let allBBoxVisible = true;

  const dispatch = createEventDispatcher();

  function handleUnselectItem() {
    dispatch("unselectItem");
  }

  function getItemById(id: string) {
    for (let category of annotations) {
      for (let label of category.labels) {
        if (label.id === id) {
          return label;
        }
      }
    }
  }

  function handleCategoryVisibility() {
    console.log("ExplorationWorkspace.handleCategoryVisibility");
    if (allBBoxVisible) {
      for (let bbox of bboxes) {
        bbox.visible = getItemById(bbox.id).visible;
      }
      bboxes = bboxes;
    }
    for (let mask of masks) {
      mask.visible = getItemById(mask.id).visible;
    }
    masks = masks;
  }

  function handleBboxesVisibility(event) {
    console.log("ExplorationWorkspace.handleBboxesVisibility");
    allBBoxVisible = event.detail;
    for (let bbox of bboxes) {
      bbox.visible = allBBoxVisible && getItemById(bbox.id).visible;
    }
    bboxes = bboxes;
  }

  function handleMaskOpacity() {
    console.log("ExplorationWorkspace.handleMaskOpacity");
    for (let mask of masks) {
      mask.opacity = getItemById(mask.id).opacity;
    }
    masks = masks;
  }

  async function handleKeyPress(e) {
    if (e.keyCode == 27) handleUnselectItem(); // Escape key pressed
  }

  onMount(async () => {
    if (annotations) {
      console.log("ExplorationWorkspace.onMount");
      categoryColor = utils.getColor(annotations.map((cat) => cat.id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("ExplorationWorkspace.afterUpdate");
      categoryColor = utils.getColor(annotations.map((cat) => cat.id)); // Define a color map for each category id
      annotations = annotations;
    }
  });
</script>

<div class="flex h-full w-full bg-zinc-100 dark:bg-zinc-900">
  {#if selectedItem}
    <Canvas2D
      itemId={selectedItem.id}
      views={selectedItem.views}
      {selectedTool}
      {categoryColor}
      {masks}
      {bboxes}
    />
    {#if annotations}
      <ExplorationPanel
        {features}
        {annotations}
        on:categoryVisibility={handleCategoryVisibility}
        on:bboxesVisibility={handleBboxesVisibility}
        on:maskOpacity={handleMaskOpacity}
      />
    {/if}
  {/if}
</div>

<!-- Pixano Explorer footer -->
<div
  class="absolute bottom-0 right-0 px-2 py-1 text-sm border-t border-l rounded-tl-lg
  text-zinc-500 dark:text-zinc-300
  bg-zinc-50 dark:bg-zinc-800
  border-zinc-300 dark:border-zinc-500"
>
  Pixano Explorer
</div>

<svelte:window on:keydown={handleKeyPress} />
