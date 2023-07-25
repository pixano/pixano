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

  import {
    AnnotationToolbar,
    Canvas2D,
    LabelToolbar,
    tools,
  } from "@pixano/canvas2d";
  import { ConfirmModal, utils, WarningModal } from "@pixano/core";

  import { interactiveSegmenterModel } from "../stores";
  import AnnotationPanel from "./AnnotationPanel.svelte";

  import type {
    ItemData,
    Mask,
    AnnotationCategory,
    AnnotationLabel,
    ViewData,
    Dataset,
    DatasetItem,
  } from "@pixano/core";

  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  // Exports
  export let selectedDataset: Dataset;
  export let selectedItem: ItemData;
  export let embeddings = {};
  export let classes;
  export let annotations: Array<AnnotationCategory>;
  export let masks: Array<Mask>;
  export let currentPage: number;
  export let saveFlag: boolean;

  const dispatch = createEventDispatcher();

  let currentAnnCategory = "";
  let categoryNameModal = false;

  let selectItemModal = false;

  let currentAnn: InteractiveImageSegmenterOutput = null;

  export let tools_lists: tools.Tool[][] = [];
  const imageTools: tools.Tool[] = [];
  const annotationTools: tools.Tool[] = [];
  let pointPlusTool = tools.createLabeledPointTool(1);
  let pointMinusTool = tools.createLabeledPointTool(0);
  let rectangleTool = tools.createRectangleTool();
  let deleteTool = tools.createDeleteTool();
  let panTool = tools.createPanTool();

  annotationTools.push(
    tools.createMultiModalTool("Point selection", tools.ToolType.LabeledPoint, [
      pointPlusTool,
      pointMinusTool,
    ])
  );
  annotationTools.push(rectangleTool);
  annotationTools.push(deleteTool);
  imageTools.push(panTool);
  tools_lists.push(imageTools);
  tools_lists.push(annotationTools);

  let selectedTool: tools.Tool = pointPlusTool;

  interactiveSegmenterModel.subscribe((segmenter) => {
    if (segmenter) {
      pointPlusTool.postProcessor = segmenter;
      pointMinusTool.postProcessor = segmenter;
      rectangleTool.postProcessor = segmenter;
    }
  });

  let categoryColor;

  function until(conditionFunction) {
    const poll = (resolve) => {
      if (conditionFunction()) resolve();
      else setTimeout((_) => poll(resolve), 400);
    };
    return new Promise(poll);
  }

  function handleKeyPress(event) {
    if (event.key === "Enter" || event.keyCode === 13) handleAddCurrentAnn();
  }

  function handleAddCurrentAnn() {
    console.log("AnnotationWorkspace.handleAddCurrentAnn");
    if (currentAnn) {
      // Check if category name provided
      if (currentAnnCategory === "") {
        categoryNameModal = true;
        return;
      }

      // Add current annotation
      addCurrentAnn();
      dispatch("enableSaveFlag");
    }
  }

  function addCurrentAnn() {
    // Set a new label
    const newLabel: AnnotationLabel = {
      id: currentAnn.id,
      viewId: currentAnn.viewId,
      sourceId: "Pixano Annotator",
      type: "mask",
      opacity: 1.0,
      visible: true,
    };

    // Add the new label's category to the class list if it doesn't already exist.
    if (!classes.some((cls) => cls.name === currentAnnCategory)) {
      // Hack to force update
      let newClasses = classes;
      let newClassId = Math.max(...newClasses.map((o) => o.id)) + 1;
      newClasses.push({ id: newClassId, name: currentAnnCategory });
      classes = newClasses;
    }

    // Check if the new label's category already exists in the current annotations
    const existingCategory = annotations.find(
      (cat) =>
        cat.name === currentAnnCategory && cat.viewId === currentAnn.viewId
    );
    if (existingCategory) {
      existingCategory.labels.push(newLabel);
      existingCategory.visible = true;
      currentAnn.label = existingCategory.name;
      currentAnn.catId = existingCategory.id;
    } else {
      const newCategory: AnnotationCategory = {
        id: classes.find((obj) => obj.name === currentAnnCategory).id,
        name: currentAnnCategory,
        viewId: currentAnn.viewId,
        labels: [newLabel],
        visible: true,
      };
      annotations.push(newCategory);
      currentAnn.label = newCategory.name;
      currentAnn.catId = newCategory.id;
    }

    // Validate current annotation
    currentAnn.validated = true;

    // Update visibility
    annotations = annotations;
  }

  async function handleChangeSelectedItem(event) {
    console.log("AnnotationWorkspace.handleChangeSelectedItem");
    const newItemId: string = event.detail.find((feature) => {
      return feature.name === "id";
    }).value;

    if (newItemId !== selectedItem.id) {
      if (!saveFlag) {
        changeSelectedItem(newItemId, event.detail);
      } else {
        selectItemModal = true;
        await until((_) => selectItemModal == false);
        if (!saveFlag) {
          changeSelectedItem(newItemId, event.detail);
        }
      }
    }
  }

  function changeSelectedItem(newItemId: string, item: DatasetItem) {
    const newItemViews: Array<ViewData> = [];
    for (let itemFeature of item) {
      if (itemFeature.dtype === "image") {
        newItemViews.push({
          id: itemFeature.name,
          url: itemFeature.value,
        });
      }
    }
    selectedItem.views = newItemViews;
    selectedItem = selectedItem;
    dispatch("selectItem", { id: newItemId });
  }

  function handleDeleteLabel(event) {
    console.log("AnnotationWorkspace.handleDeleteLabel");
    const labelId = event.detail.id;

    // Find the category that contains the item
    const labelCategory = annotations.find((cat) =>
      cat.labels.some((label) => label.id === labelId)
    );

    if (labelCategory) {
      // Filter out the item from the category
      labelCategory.labels = labelCategory.labels.filter(
        (label) => label.id !== labelId
      );
      if (labelCategory.labels.length === 0) {
        annotations = annotations.filter((ann) => ann !== labelCategory);
      }
    }

    // Find the label mask
    const labelMask = masks.find((mask) => mask.id === labelId);
    if (labelMask) {
      //remove from list
      masks = masks.filter((mask) => mask.id !== labelId);
    }

    dispatch("enableSaveFlag");

    // Update visibility
    annotations = annotations;
  }

  function handleLabelVisibility(event) {
    console.log("AnnotationWorkspace.handleLabelVisibility");
    const maskToToggle = masks.find(
      (mask) =>
        mask.id === event.detail.id && mask.viewId === event.detail.viewId
    );
    maskToToggle.visible = event.detail.visible;

    // Update visibility
    masks = masks;
  }

  async function handleLoadNextPage() {
    dispatch("loadNextPage");
  }

  onMount(() => {
    if (annotations) {
      console.log("AnnotationWorkspace.onMount");
      categoryColor = utils.getColor(annotations.map((cat) => cat.id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("AnnotationWorkspace.afterUpdate");
      categoryColor = utils.getColor(annotations.map((cat) => cat.id)); // Define a color map for each category id
      annotations = annotations;
    }
    if (classes) {
      classes = classes;
    }
  });
</script>

<div class="flex h-full w-full bg-zinc-100 dark:bg-zinc-900">
  {#if selectedItem}
    <Canvas2D
      itemId={selectedItem.id}
      views={selectedItem.views}
      bind:selectedTool
      {categoryColor}
      bind:masks
      {embeddings}
      bind:currentAnn
    />
    <AnnotationToolbar {tools_lists} bind:selectedTool />
    {#if annotations}
      <AnnotationPanel
        {selectedDataset}
        bind:annotations
        {currentPage}
        {categoryColor}
        on:selectItem={handleChangeSelectedItem}
        on:deleteLabel={handleDeleteLabel}
        on:labelVisibility={handleLabelVisibility}
        on:loadNextPage={handleLoadNextPage}
      />
    {/if}
    {#if selectedTool && selectedTool.type != tools.ToolType.Pan && selectedTool.type != tools.ToolType.Delete}
      <LabelToolbar
        bind:currentAnnCategory
        bind:classes
        bind:selectedTool
        {pointPlusTool}
        {pointMinusTool}
        on:addCurrentAnn={handleAddCurrentAnn}
      />
    {/if}
    {#if categoryNameModal}
      <WarningModal
        message="Please set a category name to save your annotation."
        on:confirm={() => (categoryNameModal = false)}
      />
    {/if}
    {#if selectItemModal}
      <ConfirmModal
        message="You have unsaved changes."
        confirm="Continue without saving"
        on:confirm={() => ((saveFlag = false), (selectItemModal = false))}
        on:cancel={() => (selectItemModal = !selectItemModal)}
      />
    {/if}
  {/if}
</div>

<!-- Pixano Annotator footer -->
<div
  class="absolute bottom-0 right-0 px-2 py-1 text-sm border-t border-l rounded-tl-lg
  text-zinc-500 dark:text-zinc-300
  bg-zinc-50 dark:bg-zinc-800
  border-zinc-300 dark:border-zinc-500"
>
  Pixano Annotator
</div>

<svelte:window on:keydown={handleKeyPress} />
