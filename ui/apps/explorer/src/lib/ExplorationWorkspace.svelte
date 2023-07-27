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

  import type { ItemData, Mask, BBox, ItemLabels, Label } from "@pixano/core";

  // Exports
  export let selectedItem: ItemData;
  export let annotations: ItemLabels;
  export let classes;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;

  const dispatch = createEventDispatcher();

  // Category colors
  let categoryColor = utils.getColor(classes);

  // Filters
  let maskOpacity = 1.0;
  let bboxOpacity = 1.0;
  let confidenceThreshold = 0.5;

  // Tools
  let panTool = tools.createPanTool();
  let selectedTool: tools.Tool = panTool;

  function handleLabelVisibility(label: Label) {
    if (label.type === "mask") {
      const mask = masks.find(
        (mask) => mask.id === label.id && mask.viewId === label.viewId
      );
      mask.visible = label.visible;
      mask.opacity = label.opacity;
    } else if (label.type === "bbox") {
      const bbox = bboxes.find(
        (bbox) => bbox.id === label.id && bbox.viewId === label.viewId
      );
      bbox.visible = label.visible;
      bbox.opacity = label.opacity;
    }

    // Update visibility
    masks = masks;
    bboxes = bboxes;
  }

  function handleLabelFilters() {
    for (let source of Object.values(annotations)) {
      for (let view of Object.values(source.views)) {
        for (let category of Object.values(view.categories)) {
          for (let label of Object.values(category.labels)) {
            // Mask opacity filter
            if (label.type === "mask") {
              label.opacity = maskOpacity;
            }
            // BBox opacity filter
            if (label.type == "bbox") {
              label.opacity = bboxOpacity;
            }
            // Confidence threshold filter
            if (label.confidence) {
              label.visible =
                label.confidence >= confidenceThreshold &&
                category.visible &&
                view.visible &&
                source.visible;
            }
            handleLabelVisibility(label);
          }
        }
      }
    }
  }

  async function handleKeyPress(e) {
    if (e.keyCode == 27) dispatch("unselectItem"); // Escape key pressed
  }

  onMount(async () => {
    if (annotations) {
      console.log("ExplorationWorkspace.onMount");
      categoryColor = utils.getColor(classes);
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("ExplorationWorkspace.afterUpdate");
      categoryColor = utils.getColor(classes);
    }
    annotations = annotations;
    classes = classes;
    masks = masks;
    bboxes = bboxes;
    handleLabelFilters();
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
        {categoryColor}
        bind:maskOpacity
        bind:bboxOpacity
        bind:confidenceThreshold
        on:labelVisibility={(event) => handleLabelVisibility(event.detail)}
        on:labelOpacity={handleLabelFilters}
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
