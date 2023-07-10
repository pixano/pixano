<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  // Imports
  import { afterUpdate, createEventDispatcher, onMount } from "svelte";

  import Canvas2D from "../../../../components/Canvas2D/src/Canvas2D.svelte";
  import { createPanTool } from "../../../../components/Canvas2D/src/tools";
  import { getColor } from "../../../../components/core/src/utils";
  import AnnotationInspector from "./AnnotationInspector.svelte";

  import type {
    ItemData,
    MaskGT,
    BBox,
    AnnotationsLabels,
  } from "../../../../components/Canvas2D/src/interfaces";

  // Exports
  export let itemData: ItemData;
  export let masksGT: Array<MaskGT>;
  export let bboxes: Array<BBox>;
  export let annotations: Array<AnnotationsLabels>;
  export let features = null;

  let panTool = createPanTool();
  let categoryColor;

  let allBBoxVisible = true;

  const dispatch = createEventDispatcher();

  function handleCloseClick() {
    dispatch("closeclick");
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

  function handleCatVisChanged(event) {
    if (allBBoxVisible) {
      for (let bbox of bboxes) {
        bbox.visible = getItemById(bbox.id).visible;
      }
      bboxes = bboxes;
    }
    for (let mask of masksGT) {
      mask.visible = getItemById(mask.id).visible;
    }
    masksGT = masksGT;
  }

  function handleAllBBoxVisChanged(event) {
    allBBoxVisible = event.detail;
    for (let bbox of bboxes) {
      bbox.visible = allBBoxVisible && getItemById(bbox.id).visible;
    }
    bboxes = bboxes;
  }

  function handleMaskOpacity(event) {
    for (let mask of masksGT) {
      mask.opacity = getItemById(mask.id).opacity;
    }
    masksGT = masksGT;
  }

  async function handleKeyDown(e) {
    if (e.keyCode == 27) handleCloseClick(); // Escape key pressed
  }

  onMount(async () => {
    //features = await getItemDetails(datasetId, rowIndex);
    console.log("DatasetItemDetails - onMount", itemData, masksGT, annotations);
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
      annotations = annotations;
    }
  });
</script>

<div class="flex h-full w-full">
  {#if itemData}
    <Canvas2D
      itemId={itemData.id}
      views={itemData.views}
      selectedTool={panTool}
      prediction={null}
      {masksGT}
      {bboxes}
      {categoryColor}
    />
    <AnnotationInspector
      {features}
      bind:annotations
      on:toggleCatVis={handleCatVisChanged}
      on:toggleAllBBoxVis={handleAllBBoxVisChanged}
      on:changeMaskOpacity={handleMaskOpacity}
    />
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

<svelte:window on:keydown={handleKeyDown} />
