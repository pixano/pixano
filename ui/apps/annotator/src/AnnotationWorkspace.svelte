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
    CategoryToolbar,
    LabelPanel,
    tools,
  } from "@pixano/canvas2d";
  import { ConfirmModal, utils, WarningModal } from "@pixano/core";

  import { interactiveSegmenterModel } from "./stores";

  import type {
    BBox,
    CategoryData,
    Dataset,
    DatasetItem,
    ItemData,
    ItemLabels,
    Label,
    Mask,
  } from "@pixano/core";

  import type { InteractiveImageSegmenter, InteractiveImageSegmenterOutput } from "@pixano/models";

  // Exports
  export let selectedDataset: Dataset;
  export let selectedItem: ItemData;
  export let annotations: ItemLabels;
  export let classes: Array<CategoryData>;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;
  export let embeddings = {};
  export let currentPage: number;
  export let saveFlag: boolean;
  export let activeLearningFlag: boolean;

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
  let currentAnnCatName = "";
  const currentAnnSource = "Pixano Annotator";

  // Tools
  const tools_lists: Array<Array<tools.Tool>> = [];
  const imageTools: Array<tools.Tool> = [];
  const classificationTools: Array<tools.Tool> = [];
  const annotationTools: Array<tools.Tool> = [];
  const pointPlusTool = tools.createLabeledPointTool(1);
  const pointMinusTool = tools.createLabeledPointTool(0);
  const rectangleTool = tools.createRectangleTool();
  const deleteTool = tools.createDeleteTool();
  const panTool = tools.createPanTool();
  const classifTool = tools.createClassifTool();
  annotationTools.push(
    tools.createMultiModalTool("Point selection", tools.ToolType.LabeledPoint, [
      pointPlusTool,
      pointMinusTool,
    ]),
  );
  annotationTools.push(rectangleTool);
  annotationTools.push(deleteTool);
  classificationTools.push(classifTool);
  imageTools.push(panTool);
  tools_lists.push(imageTools);
  tools_lists.push(classificationTools);
  tools_lists.push(annotationTools);
  let selectedTool: tools.Tool = selectedItem.features.find((f) => f.name === "label")
    ? classifTool
    : pointPlusTool;

  // Segmentation model
  interactiveSegmenterModel.subscribe((segmenter) => {
    if (segmenter) {
      pointPlusTool.postProcessor = segmenter as InteractiveImageSegmenter;
      pointMinusTool.postProcessor = segmenter as InteractiveImageSegmenter;
      rectangleTool.postProcessor = segmenter as InteractiveImageSegmenter;
    }
  });

  function until(conditionFunction: () => boolean): Promise<() => void> {
    const poll = (resolve) => {
      if (conditionFunction()) resolve();
      else setTimeout(() => poll(resolve), 400);
    };
    return new Promise(poll);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") handleAddCurrentAnn();
  }

  function handleAddClassification() {
    console.log("AnnotationWorkspace.handleAddClassification");
    if (currentAnnCatName !== "") {
      addCurrentFeatures();
      dispatch("enableSaveFlag");
    }
  }

  function addCurrentFeatures() {
    let labelExists = false;
    for (let feat of selectedItem.features) {
      if (feat["name"] === "label" && !labelExists) {
        // TODO get label from "editables"(? - to define)
        feat["value"] = currentAnnCatName;
        // Update visibility
        selectedItem = selectedItem;
        labelExists = true;
      }
    }
    if (!labelExists) {
      selectedItem.features.push({
        name: "label",
        dtype: "text",
        value: currentAnnCatName,
      });
    }
  }

  function handleAddCurrentAnn() {
    console.log("AnnotationWorkspace.handleAddCurrentAnn");
    if (currentAnn) {
      // Check if category name provided
      if (currentAnnCatName === "") {
        categoryNameModal = true;
      } else {
        addCurrentAnn();
        dispatch("enableSaveFlag");
      }
    }
  }

  function addCurrentAnn() {
    // Add the new label's category to the class list if it doesn't already exist.
    let currentAnnCatId: number;

    if (!classes.some((c) => c.name === currentAnnCatName)) {
      if (classes.length > 0) {
        currentAnnCatId = Math.max(...classes.map((o) => o.id)) + 1;
      } else {
        currentAnnCatId = 1;
      }
      classes.push({ id: currentAnnCatId, name: currentAnnCatName });
    } else {
      currentAnnCatId = classes.find((obj) => obj.name === currentAnnCatName).id;
    }

    // Add current mask
    const currentMask = <Mask>{
      id: currentAnn.id,
      viewId: currentAnn.viewId,
      svg: currentAnn.output.masksImageSVG,
      rle: currentAnn.output.rle,
      catId: currentAnnCatId,
      visible: true,
      opacity: 1.0,
    };
    masks.push(currentMask);

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
    if (!annotations[currentAnnSource].views[currentAnn.viewId].categories[currentAnnCatId]) {
      annotations[currentAnnSource].views[currentAnn.viewId].categories[currentAnnCatId] = {
        labels: {},
        id: currentAnnCatId,
        name: currentAnnCatName,
        opened: true,
        visible: true,
      };
    }

    const currentLabel = <Label>{
      id: currentAnn.id,
      categoryId: currentAnnCatId,
      categoryName: currentAnnCatName,
      sourceId: currentAnnSource,
      viewId: currentAnn.viewId,
      maskOpacity: 1.0,
      bboxOpacity: 1.0,
      visible: true,
    };
    annotations[currentAnnSource].views[currentAnn.viewId].categories[currentAnnCatId].labels[
      currentAnn.id
    ] = currentLabel;

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
    const newItemId = item.find((feature) => {
      return feature.name === "id";
    }).value as string;

    if (newItemId !== selectedItem.id) {
      if (!saveFlag) {
        changeSelectedItem(newItemId, item);
      } else {
        selectItemModal = true;
        await until(() => selectItemModal == false);
        if (!saveFlag) {
          changeSelectedItem(newItemId, item);
        }
      }
    }
  }

  function changeSelectedItem(newItemId: string, item: DatasetItem) {
    currentAnnCatName = "";
    for (const itemFeature of item) {
      if (itemFeature.dtype === "image") {
        selectedItem.views[itemFeature.name] = {
          id: itemFeature.name,
          uri: itemFeature.value as string,
        };
      }
    }
    selectedItem = selectedItem;
    dispatch("selectItem", newItemId);
  }

  function handleDeleteLabel(label: Label) {
    console.log("AnnotationWorkspace.handleDeleteLabel");

    // Remove from annotations
    delete annotations[label.sourceId].views[label.viewId].categories[label.categoryId].labels[
      label.id
    ];
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
    return utils.colorLabel(range.map((i) => i.toString())) as (id: string) => string;
  }

  function handleLoadNextPage() {
    dispatch("loadNextPage");
  }

  onMount(() => {
    if (annotations) {
      console.log("AnnotationWorkspace.onMount");
      labelColors = handleLabelColors();
    }
  });

  afterUpdate(() => {
    console.log("AnnotationWorkspace.afterUpdate");
    annotations = annotations;
    classes = classes;
    masks = masks;
    bboxes = bboxes;
    handleLabelFilters();
  });
</script>

<div class="flex h-full w-full pt-20 bg-slate-100">
  {#if selectedItem}
    <Canvas2D
      {selectedItem}
      bind:selectedTool
      {labelColors}
      {masks}
      {bboxes}
      {embeddings}
      bind:currentAnn
    />
    <AnnotationToolbar {tools_lists} bind:selectedTool />
    {#if annotations}
      <LabelPanel
        {selectedItem}
        {annotations}
        {labelColors}
        bind:maskOpacity
        bind:bboxOpacity
        bind:confidenceThreshold
        {selectedDataset}
        {currentPage}
        bind:activeLearningFlag
        on:labelVisibility={(event) => handleLabelVisibility(event.detail)}
        on:labelFilters={handleLabelFilters}
        on:deleteLabel={(event) => handleDeleteLabel(event.detail)}
        on:selectItem={(event) => handleChangeSelectedItem(event.detail)}
        on:loadNextPage={handleLoadNextPage}
      />
    {/if}
    {#if selectedTool && selectedTool.type == tools.ToolType.Classification}
      <!-- TODO WIP -->
      <CategoryToolbar
        bind:currentAnnCatName
        bind:classes
        bind:selectedTool
        {pointPlusTool}
        {pointMinusTool}
        {labelColors}
        placeholder="Label name"
        on:addCurrentAnn={handleAddClassification}
      />
    {:else if selectedTool && (selectedTool.type == tools.ToolType.LabeledPoint || selectedTool.type == tools.ToolType.Rectangle)}
      <CategoryToolbar
        bind:currentAnnCatName
        bind:classes
        bind:selectedTool
        {pointPlusTool}
        {pointMinusTool}
        {labelColors}
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
  text-slate-500 bg-slate-50 border-slate-300"
>
  Pixano Annotator
</div>

<svelte:window on:keydown={handleKeyDown} />
