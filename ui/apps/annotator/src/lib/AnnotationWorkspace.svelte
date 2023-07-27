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

  // Modals
  let categoryNameModal = false;
  let selectItemModal = false;

  // Category colors
  let colorMode = "category";
  let labelColors = handleLabelColors();

  // Filters
  let maskOpacity = 1.0;
  let bboxOpacity = 0.0;
  let confidenceThreshold = 1.0;

  // Current annotations
  let currentAnn: InteractiveImageSegmenterOutput = null;
  let currentAnnCategory = "";
  let currentAnnSource = "Pixano Annotator";

  // Tools
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

  // Segmentation model
  interactiveSegmenterModel.subscribe((segmenter) => {
    if (segmenter) {
      pointPlusTool.postProcessor = segmenter;
      pointMinusTool.postProcessor = segmenter;
      rectangleTool.postProcessor = segmenter;
    }
  });

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
    // Add current mask
    const currentMask = <Mask>{
      id: `${currentAnn.id}_mask`,
      viewId: currentAnn.viewId,
      svg: currentAnn.output.masksImageSVG,
      rle: currentAnn.output.rle,
      catId: currentAnn.catId,
      visible: true,
      opacity: 1.0,
    };
    masks.push(currentMask);

    // Add the new label's category to the class list if it doesn't already exist.
    if (!classes.some((cls) => cls.name === currentAnnCategory)) {
      // Hack to force update
      let newClasses = classes;
      let newClassId = Math.max(...newClasses.map((o) => o.id)) + 1;
      newClasses.push({ id: newClassId, name: currentAnnCategory });
      classes = newClasses;
    }

    // Check if the new label's view already exists in the current annotations
    if (!annotations[currentAnnSource]) {
      annotations[currentAnnSource] = {
        id: currentAnnSource,
        views: {},
        numLabels: 0,
        opened: true,
        visible: true,
      };
    }

    // Check if the new label's view already exists in the current annotations
    if (!annotations[currentAnnSource].views[currentAnn.viewId]) {
      annotations[currentAnnSource].views[currentAnn.viewId] = {
        id: currentAnn.viewId,
        categories: {},
        numLabels: 0,
        opened: true,
        visible: true,
      };
    }

    // Check if the new label's category already exists in the current annotations
    if (
      !annotations[currentAnnSource].views[currentAnn.viewId].categories[
        currentAnnCategory
      ]
    ) {
      annotations[currentAnnSource].views[currentAnn.viewId].categories[
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
      sourceId: currentAnnSource,
      viewId: currentAnn.viewId,
      type: "mask",
      opacity: 1.0,
      visible: true,
    };
    annotations[currentAnnSource].views[currentAnn.viewId].categories[
      currentAnnCategory
    ].labels[`${currentAnn.id}_mask`] = currentLabel;

    annotations[currentAnnSource].numLabels += 1;
    annotations[currentAnnSource].views[currentAnn.viewId].numLabels += 1;

    // Validate current annotation
    currentAnn.validated = true;

    // Update visibility
    masks = masks;
    annotations = annotations;
  }

  async function handleChangeSelectedItem(item: DatasetItem) {
    console.log("AnnotationWorkspace.handleChangeSelectedItem");
    const newItemId: string = item.find((feature) => {
      return feature.name === "id";
    }).value;

    if (newItemId !== selectedItem.id) {
      if (!saveFlag) {
        changeSelectedItem(newItemId, item);
      } else {
        selectItemModal = true;
        await until((_) => selectItemModal == false);
        if (!saveFlag) {
          changeSelectedItem(newItemId, item);
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
    dispatch("selectItem", newItemId);
  }

  function handleDeleteLabel(label: Label) {
    console.log("AnnotationWorkspace.handleDeleteLabel");

    // Remove from annotations
    delete annotations[label.sourceId].views[label.viewId].categories[
      label.categoryName
    ].labels[label.id];
    annotations[label.sourceId].numLabels -= 1;
    annotations[label.sourceId].views[label.viewId].numLabels -= 1;

    // Remove from masks / bboxes
    masks = masks.filter((mask) => mask.id !== label.id);
    bboxes = bboxes.filter((bbox) => bbox.id !== label.id);

    dispatch("enableSaveFlag");

    // Update visibility
    annotations = annotations;
  }

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
    return utils.colorLabel(range);
  }

  async function handleLoadNextPage() {
    dispatch("loadNextPage");
  }

  onMount(() => {
    if (annotations) {
      console.log("AnnotationWorkspace.onMount");
      labelColors = handleLabelColors();
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("AnnotationWorkspace.afterUpdate");
      labelColors = handleLabelColors();
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
      bind:selectedTool
      {labelColors}
      {masks}
      {bboxes}
      {embeddings}
      bind:currentAnn
    />
    <AnnotationToolbar {tools_lists} bind:selectedTool />
    {#if annotations}
      <AnnotationPanel
        {selectedItem}
        {selectedDataset}
        {annotations}
        {currentPage}
        {labelColors}
        bind:maskOpacity
        bind:bboxOpacity
        bind:confidenceThreshold
        on:selectItem={(event) => handleChangeSelectedItem(event.detail)}
        on:deleteLabel={(event) => handleDeleteLabel(event.detail)}
        on:labelVisibility={(event) => handleLabelVisibility(event.detail)}
        on:labelFilters={handleLabelFilters}
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
