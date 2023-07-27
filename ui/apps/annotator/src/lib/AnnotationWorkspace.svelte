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
    BBox,
    ItemData,
    Mask,
    ViewData,
    Dataset,
    DatasetItem,
    ItemLabels,
    Label,
  } from "@pixano/core";

  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  // Exports
  export let selectedDataset: Dataset;
  export let selectedItem: ItemData;
  export let annotations: ItemLabels;
  export let classes;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;
  export let embeddings = {};
  export let currentPage: number;
  export let saveFlag: boolean;

  const dispatch = createEventDispatcher();

  const ANN_SOURCE = "Pixano Annotator";

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

  function handleAddCurrentMask(mask: Mask) {
    masks.push(mask);
    masks = masks;
    annotations = annotations;
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
    // Add the new label's category to the class list if it doesn't already exist.
    if (!classes.some((cls) => cls.name === currentAnnCategory)) {
      // Hack to force update
      let newClasses = classes;
      let newClassId = Math.max(...newClasses.map((o) => o.id)) + 1;
      newClasses.push({ id: newClassId, name: currentAnnCategory });
      classes = newClasses;
    }

    // Check if the new label's view already exists in the current annotations
    if (!annotations[ANN_SOURCE]) {
      annotations[ANN_SOURCE] = {
        id: ANN_SOURCE,
        views: {},
        numLabels: 0,
        opened: true,
        visible: true,
      };
    }

    // Check if the new label's view already exists in the current annotations
    if (!annotations[ANN_SOURCE].views[currentAnn.viewId]) {
      annotations[ANN_SOURCE].views[currentAnn.viewId] = {
        id: currentAnn.viewId,
        categories: {},
        numLabels: 0,
        opened: true,
        visible: true,
      };
    }

    // Check if the new label's category already exists in the current annotations
    if (
      !annotations[ANN_SOURCE].views[currentAnn.viewId].categories[
        currentAnnCategory
      ]
    ) {
      annotations[ANN_SOURCE].views[currentAnn.viewId].categories[
        currentAnnCategory
      ] = {
        labels: {},
        id: classes.find((obj) => obj.name === currentAnnCategory).id,
        name: currentAnnCategory,
        opened: true,
        visible: true,
      };
    }

    const currentLabel = <Label>{
      id: `${currentAnn.id}_mask`,
      categoryId: classes.find((obj) => obj.name === currentAnnCategory).id,
      categoryName: currentAnnCategory,
      sourceId: ANN_SOURCE,
      viewId: currentAnn.viewId,
      type: "mask",
      opacity: 1.0,
      visible: true,
    };
    annotations[ANN_SOURCE].views[currentAnn.viewId].categories[
      currentAnnCategory
    ].labels[`${currentAnn.id}_mask`] = currentLabel;

    annotations[ANN_SOURCE].numLabels += 1;
    annotations[ANN_SOURCE].views[currentAnn.viewId].numLabels += 1;

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
    currentAnnCategory = "";
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
    const sourceId = event.detail.sourceId;
    const viewId = event.detail.viewId;
    const categoryName = event.detail.categoryName;
    const labelId = event.detail.labelId;

    // Remove from annotations
    delete annotations[sourceId].views[viewId].categories[categoryName].labels[
      labelId
    ];
    annotations[sourceId].numLabels -= 1;
    annotations[sourceId].views[viewId].numLabels -= 1;

    // Remove from masks / bboxes
    masks = masks.filter((mask) => mask.id !== labelId);
    bboxes = bboxes.filter((bbox) => bbox.id !== labelId);

    dispatch("enableSaveFlag");

    // Update visibility
    annotations = annotations;
  }

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
      bbox.opacity = event.detail.opacity;
    }

    // Update visibility
    masks = masks;
    bboxes = bboxes;
  }

  async function handleLoadNextPage() {
    dispatch("loadNextPage");
  }

  onMount(() => {
    if (annotations) {
      console.log("AnnotationWorkspace.onMount");
      categoryColor = utils.getColor(classes.map((cat) => cat.id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("AnnotationWorkspace.afterUpdate");
      categoryColor = utils.getColor(classes.map((cat) => cat.id)); // Define a color map for each category id
      annotations = annotations;
    }
    classes = classes;
    masks = masks;
    bboxes = bboxes;
  });
</script>

<div class="flex h-full w-full bg-zinc-100 dark:bg-zinc-900">
  {#if selectedItem}
    <Canvas2D
      itemId={selectedItem.id}
      views={selectedItem.views}
      bind:selectedTool
      {categoryColor}
      {masks}
      {bboxes}
      {embeddings}
      bind:currentAnn
      on:addCurrentMask={(event) => handleAddCurrentMask(event.detail)}
    />
    <AnnotationToolbar {tools_lists} bind:selectedTool />
    {#if annotations}
      <AnnotationPanel
        {selectedItem}
        {selectedDataset}
        {annotations}
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
