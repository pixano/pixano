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

  import { Canvas2D, LabelPanel, tools } from "@pixano/canvas2d";
  import { utils } from "@pixano/core";

  import type { BBox, DatasetCategory, DatasetItem, Mask, ItemLabels, Label } from "@pixano/core";

  // Exports
  export let selectedItem: DatasetItem;
  export let annotations: ItemLabels;
  export let classes: Array<DatasetCategory>;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;

  const dispatch = createEventDispatcher();

  // Category colors
  let colorMode = "category";
  let colorScale = handleLabelColors();

  // Filters
  let maskOpacity = 1.0;
  let bboxOpacity = 1.0;
  let confidenceThreshold = 0.0;

  // Tools
  const panTool = tools.createPanTool();
  const selectedTool: tools.Tool = panTool;

  function handleLabelVisibility(label: Label) {
    // Try and find a mask
    const mask = masks.find((mask) => mask.id === label.id && mask.viewId === label.viewId);
    if (mask) {
      mask.visible = label.visible;
      mask.opacity = label.maskOpacity;
    }

    // Try and find a bbox
    const bbox = bboxes.find((bbox) => bbox.id === label.id && bbox.viewId === label.viewId);
    if (bbox) {
      bbox.visible = label.visible;
      bbox.opacity = label.bboxOpacity;
    }

    // Update visibility
    masks = masks;
    bboxes = bboxes;
  }

  function handleLabelFilters() {
    for (const source of Object.values(annotations)) {
      for (const view of Object.values(source.views)) {
        for (const category of Object.values(view.categories)) {
          for (const label of Object.values(category.labels)) {
            // Opacity filters
            label.maskOpacity = maskOpacity;
            label.bboxOpacity = bboxOpacity;
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

  function handleLabelColors() {
    let range: Array<number>;
    if (colorMode === "category") {
      range = [
        Math.min(...classes.map((cat) => cat.id)),
        Math.max(...classes.map((cat) => cat.id)),
      ];
    } else if (colorMode === "source") {
      range = [0, Object.keys(annotations).length];
    }
    return utils.ordinalColorScale(range.map((i) => i.toString())) as (id: string) => string;
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key == "Escape") dispatch("unselectItem");
  }

  onMount(() => {
    if (annotations) {
      console.log("ExplorationWorkspace.onMount");
      colorScale = handleLabelColors();
    }
  });

  afterUpdate(() => {
    console.log("ExplorationWorkspace.afterUpdate");
    annotations = annotations;
    classes = classes;
    masks = masks;
    bboxes = bboxes;
    handleLabelFilters();
  });
</script>

<div class="flex h-full w-full pt-20 bg-slate-100">
  {#if selectedItem}
    <Canvas2D {selectedItem} {selectedTool} {colorScale} {masks} {bboxes} />
    {#if annotations}
      <LabelPanel
        {selectedItem}
        {annotations}
        {colorScale}
        bind:maskOpacity
        bind:bboxOpacity
        bind:confidenceThreshold
        on:labelVisibility={(event) => handleLabelVisibility(event.detail)}
        on:labelFilters={handleLabelFilters}
      />
    {/if}
  {/if}
</div>

<!-- Pixano Explorer footer -->
<div
  class="absolute bottom-0 right-0 px-2 py-1 text-sm border-t border-l rounded-tl-lg
  text-slate-500 bg-slate-50 border-slate-300"
>
  Pixano Explorer
</div>

<svelte:window on:keydown={handleKeyDown} />
