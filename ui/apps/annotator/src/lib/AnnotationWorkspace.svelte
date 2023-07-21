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
    DatasetItems,
    DatasetItemFeature,
  } from "@pixano/core";

  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  // Exports
  export let selectedItem: ItemData;
  export let embeddings = {};
  export let classes;
  export let annotations: Array<AnnotationCategory>;
  export let masks: Array<Mask>;
  export let datasetItems: DatasetItems;
  export let currentPage: number;
  export let saveFlag: boolean;

  const dispatch = createEventDispatcher();

  let className = "";
  let classNameWarning = false;

  let selectItemConfirm = false;

  let prediction: InteractiveImageSegmenterOutput = null;

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
    console.log("Interactive Segmenter set in the workspace");
    console.log(segmenter);
    if (segmenter) {
      pointPlusTool.postProcessor = segmenter;
      pointMinusTool.postProcessor = segmenter;
      rectangleTool.postProcessor = segmenter;
    }
  });

  let categoryColor;

  // events handlers
  function handleKeyPress(event) {
    if (event.key === "Enter" || event.keyCode === 13) handleValidate();
  }

  function until(conditionFunction) {
    const poll = (resolve) => {
      if (conditionFunction()) resolve();
      else setTimeout((_) => poll(resolve), 400);
    };
    return new Promise(poll);
  }

  function addAnnotation(className: string, id: string, viewId: string) {
    // Check if the class already exists in the annotation array
    const existingClass = annotations.find(
      (cat) => cat.name === className && cat.viewId === viewId
    );

    // Add the class to the default class list if it doesn't already exist.
    if (!classes.some((cls) => cls.name === className)) {
      // Hack to force update
      let newClasses = classes;
      let newClassId = Math.max(...newClasses.map((o) => o.id)) + 1;
      newClasses.push({ id: newClassId, name: className });
      classes = newClasses;
    }

    if (existingClass) {
      // Set item name
      const annotation: AnnotationLabel = {
        id: id,
        viewId: viewId,
        type: "??", //TODO put annotation type (bbox/mask)
        opacity: 1.0,
        visible: true,
      };

      // If the class exists, add the item to its 'items' array
      existingClass.labels.push(annotation);
      //in case class was invisible, make it visible
      existingClass.visible = true;
    } else {
      // Set item name
      const annotation: AnnotationLabel = {
        id: id,
        viewId: viewId,
        type: "??", //TODO put annotation type (bbox/mask)
        opacity: 1.0,
        visible: true,
      };

      // If the class doesn't exist, create a new object and add it to the annotation array
      const newClass: AnnotationCategory = {
        id: classes.find((obj) => obj.name === className).id,
        name: className,
        viewId: viewId,
        labels: [annotation],
        visible: true,
      };
      annotations.push(newClass);
    }

    // Hack to force update in AnnotationPanel
    annotations = annotations;
  }

  function handleValidate() {
    if (prediction) {
      // Validate user input
      if (className === "") {
        toggleClassNameModal();
        return;
      }

      addAnnotation(className, prediction.id, prediction.viewId);

      // prediction class
      const predictionClass = annotations.find(
        (cat) => cat.name === className && cat.viewId === prediction.viewId
      );

      //validate
      prediction.label = predictionClass.name;
      prediction.catId = predictionClass.id;
      prediction.validated = true;

      dispatch("enableSaveFlag");
    }
  }

  function toggleClassNameModal() {
    classNameWarning = !classNameWarning;
  }

  function toggleSelectItemModal() {
    selectItemConfirm = !selectItemConfirm;
  }

  function confirmChangeSelectedItem() {
    saveFlag = false;
    toggleSelectItemModal();
  }

  async function handleChangeSelectedItem(event) {
    let newItemId: string = event.detail.find((feature) => {
      return feature.name === "id";
    }).value;

    if (newItemId !== selectedItem.id) {
      if (!saveFlag) {
        changeSelectedItem(newItemId, event.detail);
      } else {
        toggleSelectItemModal();
        await until((_) => selectItemConfirm == false);
        if (!saveFlag) {
          changeSelectedItem(newItemId, event.detail);
        }
      }
    }
  }

  function changeSelectedItem(newItemId: string, item: DatasetItemFeature[]) {
    let newItemViews: Array<ViewData> = [];
    for (let itemFeature of item) {
      if (itemFeature.dtype === "image") {
        newItemViews.push({
          viewId: itemFeature.name,
          imageURL: itemFeature.value,
        });
      }
    }
    selectedItem.views = newItemViews;
    selectedItem = selectedItem;
    dispatch("selectItem", { id: newItemId });
  }

  function handleDeleteLabel(event) {
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

    //hack svelte to reflect changes
    annotations = annotations;
  }

  function handleLabelVisibility(event) {
    const mask_to_toggle = masks.find(
      (mask) =>
        mask.id === event.detail.id && mask.viewId === event.detail.viewId
    );
    mask_to_toggle.visible = event.detail.visible;
    //hack svelte to reflect changes
    masks = masks;
  }

  async function handleLoadNextPage(event) {
    dispatch("loadNextPage");
  }

  onMount(() => {
    if (annotations) {
      console.log(
        "AnnotationWorkspace - onMount",
        selectedItem,
        masks,
        annotations
      );
      categoryColor = utils.getColor(annotations.map((cat) => cat.id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    // needed for annotations update
    if (annotations) {
      console.log("afterUpdate - annotations", annotations);
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
      {embeddings}
      itemId={selectedItem.id}
      views={selectedItem.views}
      bind:selectedTool
      {categoryColor}
      bind:prediction
      bind:masks
    />
    <AnnotationToolbar {tools_lists} bind:selectedTool />
    {#if annotations}
      <AnnotationPanel
        bind:annotations
        {datasetItems}
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
        bind:className
        bind:classes
        bind:selectedTool
        {pointPlusTool}
        {pointMinusTool}
        on:validate={handleValidate}
      />
    {/if}
    {#if classNameWarning}
      <WarningModal
        message="Please set a label to save your annotation."
        on:confirm={toggleClassNameModal}
      />
    {/if}
    {#if selectItemConfirm}
      <ConfirmModal
        message="You have unsaved changes."
        confirm="Continue without saving"
        on:confirm={confirmChangeSelectedItem}
        on:cancel={toggleSelectItemModal}
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
