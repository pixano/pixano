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

  import type { ItemData, Mask, BBox, ItemLabels } from "@pixano/core";

  // Exports
  export let selectedItem: ItemData;
  export let annotations: ItemLabels;
  export let classes;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;

  let panTool = tools.createPanTool();
  let selectedTool: tools.Tool = panTool;

  let categoryColor;

  const dispatch = createEventDispatcher();

  function handleLabelVisibility(event) {
    console.log("AnnotationWorkspace.handleLabelVisibility");
    if (event.detail.type === "mask") {
      const mask = masks.find(
        (mask) =>
          mask.id === event.detail.id && mask.viewId === event.detail.viewId
      );
      mask.visible = event.detail.visible;
      mask.opacity = event.detail.opacity;
    } else if (event.detail.type === "bbox") {
      const bbox = bboxes.find(
        (bbox) =>
          bbox.id === event.detail.id && bbox.viewId === event.detail.viewId
      );
      bbox.visible = event.detail.visible;
    }

    // Update visibility
    masks = masks;
    bboxes = bboxes;
  }

  async function handleKeyPress(e) {
    if (e.keyCode == 27) dispatch("unselectItem"); // Escape key pressed
  }

  onMount(async () => {
    if (annotations) {
      console.log("ExplorationWorkspace.onMount");
      categoryColor = utils.getColor(classes.map((cat) => cat.id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("ExplorationWorkspace.afterUpdate");
      categoryColor = utils.getColor(classes.map((cat) => cat.id)); // Define a color map for each category id
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
        {selectedItem}
        {annotations}
        on:labelVisibility={handleLabelVisibility}
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
