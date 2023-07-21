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

  import { Canvas2D } from "@pixano/canvas2d";
  import { createPanTool } from "@pixano/canvas2d/src/tools";
  import { getColor } from "@pixano/core/src/utils";

  import ExplorationPanel from "./ExplorationPanel.svelte";

  import type {
    ItemData,
    Mask,
    BBox,
    AnnotationsLabels,
  } from "@pixano/canvas2d/src/interfaces";

  // Exports
  export let itemData: ItemData;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;
  export let annotations: Array<AnnotationsLabels>;
  export let features = null;

  let panTool = createPanTool();
  let categoryColor;

  let allBBoxVisible = true;

  const dispatch = createEventDispatcher();

  function handleUnselectItem() {
    dispatch("unselectItem");
  }

  /**
   * get item by id from annotations
   */
  function getItemById(id: string) {
    for (let cat of annotations) {
      for (let item of cat.items) {
        if (item.id === id) {
          return item;
        }
      }
    }
  }

  function handleCategoryVisibility(event) {
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
    allBBoxVisible = event.detail;
    for (let bbox of bboxes) {
      bbox.visible = allBBoxVisible && getItemById(bbox.id).visible;
    }
    bboxes = bboxes;
  }

  function handleMaskOpacity(event) {
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
      console.log(
        "ExplorationWorkspace - onMount",
        itemData,
        masks,
        annotations
      );
      categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("afterUpdate - annotations", annotations);
      categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
      annotations = annotations;
    }
  });
</script>

<div class="flex h-full w-full bg-zinc-100 dark:bg-zinc-900">
  {#if itemData}
    <Canvas2D
      itemId={itemData.id}
      views={itemData.views}
      selectedTool={panTool}
      {categoryColor}
      prediction={null}
      {masks}
      {bboxes}
    />
    {#if annotations}
      <ExplorationPanel
        {features}
        bind:annotations
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
