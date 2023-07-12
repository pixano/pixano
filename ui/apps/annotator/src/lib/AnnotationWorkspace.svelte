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

  import AnnotationToolbar from "../../../../components/canvas2d/src/AnnotationToolbar.svelte";
  import LabelToolbar from "../../../../components/canvas2d/src/LabelToolbar.svelte";
  import Canvas2D from "../../../../components/canvas2d/src/Canvas2D.svelte";
  import {
    createLabeledPointTool,
    createMultiModalTool,
    createPanTool,
    createRectangleTool,
    type Tool,
    ToolType,
  } from "../../../../components/canvas2d/src/tools";
  import { getColor } from "../../../../components/core/src/utils";
  import { interactiveSegmenterModel } from "../stores";
  import AnnotationPanel from "./AnnotationPanel.svelte";

  import type { InteractiveImageSegmenterOutput } from "../../../../components/models/src/interactive_image_segmentation";
  import type {
    ItemData,
    MaskGT,
    AnnotationsLabels,
    AnnLabel,
    ViewData,
    DatabaseFeats,
  } from "../../../../components/canvas2d/src/interfaces";

  // Exports
  export let itemData: ItemData;
  export let embeddings = {};
  export let classes;
  export let annotations: Array<AnnotationsLabels>;
  export let masksGT: Array<MaskGT>;
  export let dbImages: DatabaseFeats;
  export let curPage: number;
  export let handleUnsavedChanges;

  const dispatch = createEventDispatcher();

  let className = "";

  let prediction: InteractiveImageSegmenterOutput = null;

  export let tools_lists: Tool[][] = [];
  const imageTools: Tool[] = [];
  const annotationTools: Tool[] = [];
  let pointPlusTool = createLabeledPointTool(1);
  let pointMinusTool = createLabeledPointTool(0);
  let rectTool = createRectangleTool();
  let panTool = createPanTool();

  imageTools.push(panTool);
  annotationTools.push(
    createMultiModalTool("Point selection", ToolType.LabeledPoint, [
      pointPlusTool,
      pointMinusTool,
    ])
  );
  annotationTools.push(rectTool);
  tools_lists.push(imageTools);
  tools_lists.push(annotationTools);

  let selectedAnnotationTool: Tool = pointPlusTool;

  interactiveSegmenterModel.subscribe((segmenter) => {
    console.log("Interactive Segmenter set in the workspace");
    console.log(segmenter);
    if (segmenter) {
      pointPlusTool.postProcessor = segmenter;
      pointMinusTool.postProcessor = segmenter;
      rectTool.postProcessor = segmenter;
    }
  });

  let categoryColor;

  // events handlers
  function handleAnnotationToolChange() {
    //console.log("New tool selected");
  }

  function handleKeyPress(event) {
    if (event.key === "Enter" || event.keyCode === 13) handleValidate();
  }

  function addAnnotation(className: string, id: string, viewId: string) {
    // Check if the class already exists in the annotation array
    const existingClass = annotations.find(
      (obj) => obj.category_name === className && obj.viewId === viewId
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
      const annotation: AnnLabel = {
        id: id,
        type: "??", //TODO put annotation type (bbox/mask)
        label: `${className} ${existingClass.items.length}`,
        visible: true,
        opacity: 1.0,
      };

      // If the class exists, add the item to its 'items' array
      existingClass.items.push(annotation);
      //in case class was invisible, make it visible
      existingClass.visible = true;
    } else {
      // Set item name
      const annotation: AnnLabel = {
        id: id,
        type: "??", //TODO put annotation type (bbox/mask)
        label: `${className} 0`,
        visible: true,
        opacity: 1.0,
      };

      // If the class doesn't exist, create a new object and add it to the annotation array
      const newClass: AnnotationsLabels = {
        viewId: viewId,
        category_name: className,
        category_id: classes.find((obj) => obj.name === className).id,
        items: [annotation],
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
        alert("Please set a class name");
        return;
      }

      addAnnotation(className, prediction.id, prediction.viewId);

      // prediction class
      const predictionClass = annotations.find(
        (obj) =>
          obj.category_name === className && obj.viewId === prediction.viewId
      );

      //validate
      prediction.label = predictionClass.category_name;
      prediction.catId = predictionClass.category_id;
      prediction.validated = true;

      dispatch("enableSaveFlag");
    }
  }

  function handleImageSelectedChange(event) {
    if (handleUnsavedChanges()) {
      let new_views: Array<ViewData> = [];
      for (let view of event.detail.views) {
        new_views.push({
          viewId: view.viewId,
          imageURL: view.img,
        });
      }
      itemData.views = new_views;
      itemData = itemData;
      dispatch("imageSelected", { id: event.detail.id });
    }
  }

  function handleItemDeleted(item) {
    const detailId = item.detail.id;

    // Find the annotation object that contains the item
    const newAnnots = annotations.find((annotation) =>
      annotation.items.some((annotatedItem) => annotatedItem.id === detailId)
    );

    if (newAnnots) {
      // Filter out the item from the items array
      newAnnots.items = newAnnots.items.filter(
        (annotatedItem) => annotatedItem.id !== detailId
      );
      if (newAnnots.items.length === 0) {
        annotations = annotations.filter((ann) => ann !== newAnnots);
      }
    }

    // Find the mask to delete from masksGT
    const mask_to_del = masksGT.find((mask) => mask.id === detailId);
    if (mask_to_del) {
      //remove from list
      masksGT = masksGT.filter((mask) => mask.id !== detailId);
    }

    dispatch("enableSaveFlag");

    //hack svelte to reflect changes
    annotations = annotations;
  }

  function handleVisibilityChange(item) {
    const mask_to_toggle = masksGT.find(
      (mask) => mask.id === item.detail.id && mask.viewId === item.detail.viewId
    );
    mask_to_toggle.visible = item.detail.visible;
    //hack svelte to reflect changes
    masksGT = masksGT;
  }

  async function handleLoadNextPage(event) {
    dispatch("loadNextPage");
  }

  onMount(() => {
    if (annotations) {
      console.log("onMount - annotations", annotations);
      categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
    }
  });

  afterUpdate(() => {
    //console.log("afterUpdate - itemData", itemData);
    //console.log("afterUpdate - masksGT", masksGT);
    //console.log("afterUpdate - annotations", annotations);
    //console.log("afterUpdate - classes", classes);

    // needed for annotations update
    if (annotations) {
      console.log("afterUpdate - annotations", annotations);
      categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
      annotations = annotations;
    }
    if (classes) {
      classes = classes;
    }
  });
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="flex h-full w-full bg-zinc-100 dark:bg-zinc-900">
  <Canvas2D
    {embeddings}
    itemId={itemData.id}
    views={itemData.views}
    selectedTool={selectedAnnotationTool}
    {categoryColor}
    bind:prediction
    bind:masksGT
    bboxes={null}
  />
  <AnnotationToolbar
    {tools_lists}
    bind:selectedTool={selectedAnnotationTool}
    on:toolSelected={handleAnnotationToolChange}
  />
  {#if annotations}
    <AnnotationPanel
      bind:annotations
      dataset={dbImages}
      lastLoadedPage={curPage}
      {categoryColor}
      on:imageSelected={handleImageSelectedChange}
      on:itemDeleted={handleItemDeleted}
      on:toggleVisibility={handleVisibilityChange}
      on:loadNextPage={handleLoadNextPage}
    />
  {/if}
  {#if selectedAnnotationTool && selectedAnnotationTool.type != ToolType.Pan}
    <LabelToolbar
      bind:className
      bind:classes
      bind:selectedAnnotationTool
      {pointPlusTool}
      {pointMinusTool}
      on:validate={handleValidate}
    />
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
