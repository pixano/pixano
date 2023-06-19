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

  import { onMount, afterUpdate, createEventDispatcher } from "svelte";

  import DataPanel from "./DataPanel.svelte";
  import NavigationToolbar from "./NavigationToolbar.svelte";
  import Canvas2D from "../../../../components/Canvas2D/src/Canvas2D.svelte";
  import CanvasToolbar from "../../../../components/Canvas2D/src/CanvasToolbar.svelte";
  import {
    type Tool,
    createLabeledPointTool,
    createRectangleTool,
    createPanTool,
    ToolType,
    createMultiModalTool,
  } from "../../../../components/Canvas2D/src/tools";
  import type { ItemData, MaskGT, AnnotationsLabels, ItemLabel } from "../../../../components/Canvas2D/src/interfaces";
  import { type InteractiveImageSegmenterOutput } from "../../../../components/models/src/interactive_image_segmentation";

  import { interactiveSegmenterModel } from "../stores";

  export let itemData: ItemData;
  export let embedding: any;
  export let classes;
  export let annotations: Array<AnnotationsLabels>;
  export let masksGT: Array<MaskGT>;
  export let dbImages = [];
  export let handleCloseClick;
  let className = "";

  let prediction: InteractiveImageSegmenterOutput = null;

  const annotationTools: Tool[] = [];
  let pointPlusTool = createLabeledPointTool(1);
  let pointMinusTool = createLabeledPointTool(0);
  let rectTool = createRectangleTool();
  let panTool = createPanTool();
  //let interactiveSegmenter;

  annotationTools.push(panTool);
  annotationTools.push(createMultiModalTool(ToolType.LabeledPoint, [pointPlusTool, pointMinusTool]));
  annotationTools.push(rectTool);

  let selectedAnnotationTool: Tool = panTool;

  interactiveSegmenterModel.subscribe((segmenter) => {
    console.log("Interactive Segmenter set in the workspace");
    console.log(segmenter);
    if (segmenter) {
      pointPlusTool.postProcessor = segmenter;
      pointMinusTool.postProcessor = segmenter;
      rectTool.postProcessor = segmenter;
    }
  });

  const dispatch = createEventDispatcher();

  // events handlers
  function handleAnnotationToolChange() {
    //console.log("New tool selected");
  }

  function handleKeyPress(event) {
    if (event.key === "Enter" || event.keyCode === 13) handleValidate();
  }

  function addAnnotation(className: string, id: string) {
    // Check if the class already exists in the annotation array
    const existingClass = annotations.find((obj) => obj.category === className);

    // Add the class to the default class list if it doesn't already exist.
    if (!classes.some((cls) => cls.name === className)) {
      // Hack to force update
      let newClasses = classes;
      newClasses.push({ id: classes.length, name: className });
      classes = newClasses;
    }

    if (existingClass) {
      // Set item name
      const annotation: ItemLabel = {
        id: id,
        label: `${className}-${existingClass.items.length}`,
        visible : true,
        opacity: 0.5,
      };

      // If the class exists, add the item to its 'items' array
      existingClass.items.push(annotation);
      //in case class was invisible, make it visible
      existingClass.visible = true;
    } else {
      // Set item name
      const annotation: ItemLabel = {
        id: id,
        label: `${className}-0`,
        visible: true,
        opacity: 0.5,
      };

      // If the class doesn't exist, create a new object and add it to the annotation array
      const newClass: AnnotationsLabels = {
        category: className,
        //category_id: "",  //TODO add a category_id ??
        items: [annotation],
        visible: true,
      };
      annotations.push(newClass);
    }

    // Hack to force update in DataPanel
    annotations = annotations;
  }

  function handleValidate() {
    if (prediction) {
      // Validate user input
      if (className === "") {
        alert("Please set a class name");
        return;
      }

      addAnnotation(className, prediction.id);

      //validate
      prediction.validated = true;
    }
  }

  function handleSaveClick() {
    dispatch("saveAnns", {anns: annotations , masks: masksGT});
  }

  function handleImageSelectedChange(img) {
    itemData.imageURL = img.detail;
    masksGT = [];
    annotations = [];
    classes = [];
  }

  function handleItemDeleted(item) {
    const detailId = item.detail.id;

    // Find the annotation object that contains the item
    const newAnnots = annotations.find((annotation) =>
      annotation.items.some((annotatedItem) => annotatedItem.id === detailId)
    );

    if (newAnnots) {
      // Filter out the item from the items array
      newAnnots.items = newAnnots.items.filter((annotatedItem) => annotatedItem.id !== detailId);
      if (newAnnots.items.length === 0) {
        annotations = annotations.filter((ann)=> ann !== newAnnots);
      }
    }

    // Find the mask to delete from masksGT
    const mask_to_del = masksGT.find(mask => mask.id === detailId);
    if (mask_to_del) {
      //remove from list
      masksGT = masksGT.filter(mask => mask.id !== detailId)
    }

    //hack svelte to reflect changes
    annotations = annotations
  }

  function handleVisibilityChange(item) {
    const mask_to_toggle = masksGT.find(mask => mask.id === item.detail.id);
    mask_to_toggle.visible = item.detail.visible;
    //hack svelte to reflect changes
    masksGT = masksGT;
  }

  //onMount(() => {});

  afterUpdate(() => {
    //console.log("afterUpdate - itemData", itemData);
    //console.log("afterUpdate - masksGT", masksGT);
    //console.log("afterUpdate - annotations", annotations);
    //console.log("afterUpdate - classes", classes);

    // needed for annotations update
    if (annotations) {
      annotations = annotations;
    }
    if(classes) {
      classes = classes;
    }
  });

</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="flex h-screen w-screen font-[Montserrat]">
  {#if selectedAnnotationTool && selectedAnnotationTool.type != ToolType.Pan}
    <div
      id="point-modal"
      class="absolute top-24 left-1/2 -translate-x-1/2 p-4 flex items-center space-x-4 bg-white rounded-lg shadow-xl z-10"
    >
      <div class="group">
        <input
          type="text"
          placeholder="New Class"
          class="py-1 px-2 border rounded focus:outline-none focus:border-rose-300 bg-[url('icons/expand.svg')] bg-no-repeat bg-right"
          bind:value={className}
        />
        

        <div
          class="absolute left-0 top-14 w-full px-2 py-2 hidden bg-white rounded-b-lg group-focus-within:flex hover:flex flex-col"
        >
          {#each classes as cls}
            <span
              class="py-1 px-2 text-sm cursor-pointer bg-white rounded-lg hover:bg-zinc-100"
              on:click={() => (className = cls.name)}
            >
              {cls.name}
            </span>
          {/each}
        </div>
      </div>

      {#if selectedAnnotationTool.type === ToolType.LabeledPoint}
        <img
          src="icons/plus.svg"
          alt="plus button"
          class="h-8 w-8 p-1 bg-white border rounded cursor-pointer hover:bg-zinc-100 {selectedAnnotationTool ===
          pointPlusTool
            ? 'border-rose-900'
            : 'border-transparent'}"
          on:click={() => {
            selectedAnnotationTool = pointPlusTool;
          }}
        />
        <img
          src="icons/minus.svg"
          alt="minus button"
          class="h-8 w-8 p-1 bg-white border rounded cursor-pointer hover:bg-zinc-100 {selectedAnnotationTool ===
          pointMinusTool
            ? 'border-rose-900'
            : 'border-transparent'}"
          on:click={() => {
            selectedAnnotationTool = pointMinusTool;
          }}
        />
      {/if}
      <img
        src="icons/ok.svg"
        alt="minus button"
        class="h-8 w-8 p-1 bg-rose-900 rounded cursor-pointer hover:bg-rose-700"
        on:click={handleValidate}
      />
    </div>
  {/if}
  <CanvasToolbar
    tools={annotationTools}
    bind:selectedTool={selectedAnnotationTool}
    on:toolSelected={handleAnnotationToolChange}
  />
  <div class="flex flex-col grow">
    <NavigationToolbar database={itemData.dbName} imageName={itemData.imageId} {handleCloseClick} {handleSaveClick} />
    <div class="flex grow">
      <Canvas2D
        imageURL={itemData.imageURL}
        imageId={itemData.imageId}
        viewId={itemData.viewId}
        selectedTool={selectedAnnotationTool}
        {embedding}
        bind:prediction
        bind:masksGT
        bboxes={null}
      />
      {#if annotations}
        <DataPanel
          bind:annotations
          {dbImages}
          on:imageSelected={handleImageSelectedChange}
          on:itemDeleted={handleItemDeleted}
          on:toggleVisibility={handleVisibilityChange}
        />
      {/if}
    </div>
  </div>
</div>
<svelte:window on:keydown={handleKeyPress} />