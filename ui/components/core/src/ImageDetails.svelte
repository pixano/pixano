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
  import { onMount, beforeUpdate, afterUpdate } from "svelte";
  import Konva from "konva";
  import * as KonvaUtils from "./konva_utils";
  import * as Utils from "./utils";
  import {
    generatePolygonSegments,
    convertSegmentsToSVG,
  } from "../../../components/models/src/tracer";

  // Represents an image's features
  export let features: any;
  let oldID: number;

  // Function that maps an id to a color
  let categoryColor = null;

  // Konva stage to draw every view
  let stage: Konva.Stage;

  // Multiview image grid
  let gridSize = {
    rows: 0,
    cols: 0,
  };

  // Filters
  let showBoundingBoxes: boolean = true;
  let maskOpacity: number = 0.5;
  let minConfidence: number = 0.5;
  let categoriesFilter: Array<number> = [];
  let viewsFilter: Array<string> = [];

  // Change every mask opacity to match the desired value.
  function updateMasksOpacity() {
    stage.children.forEach((layer) => {
      for (const group of layer.children) {
        if (group.name() === "masks")
          KonvaUtils.updateMasksOpacity(group, maskOpacity);
      }
    });
  }

  /**
   * Toggle on/off a category visibility.
   * @param category category to show/hide
   */
  function toggleCategoryVisibility(category: number) {
    // Add or remove a category from the filter.
    if (categoriesFilter.includes(category)) {
      const index = categoriesFilter.indexOf(category);
      if (index > -1) categoriesFilter.splice(index, 1);
    } else categoriesFilter.push(category);

    updateElementsVisibility();
  }

  // Show or hide every category.
  function toggleAllCategoriesVisibility() {
    // Fill or empty the category filter
    if (categoriesFilter.length == 0)
      features.categoryStats.forEach((cat) => categoriesFilter.push(cat.id));
    else categoriesFilter = [];

    updateElementsVisibility();
  }

  /**
   * Toggle on/off a view visibility
   * @param view view to show/hide
   */
  function toggleViewVisibility(view: string) {
    // Add or remove a view from the filter.
    if (viewsFilter.includes(view)) {
      const index = viewsFilter.indexOf(view);
      if (index > -1) viewsFilter.splice(index, 1);
    } else viewsFilter.push(view);

    updateElementsVisibility();
  }

  // Show or hide every view.
  function toggleAllViewsVisibility() {
    // Fill or empty the view filter
    if (viewsFilter.length == 0)
      Object.keys(features.views).forEach((view) => viewsFilter.push(view));
    else viewsFilter = [];

    updateElementsVisibility();
  }

  // Update every konva element visibility
  function updateElementsVisibility() {
    stage.children.forEach((layer) => {
      // Set layers visibility
      if (viewsFilter.includes(layer.name())) layer.hide();
      else layer.show();

      layer.children.forEach((group) => {
        // Set boxes group visibility
        if (group.name() == "boxes" || group.name() == "tooltips") {
          if (showBoundingBoxes) group.show();
          else group.hide();
        }

        // Set items visibility
        group.children.forEach((child) => {
          let id = child.id();
          let catId = parseInt(id.replace("category-", ""));
          let conf = parseFloat(id.replace("category-" + catId + "-", ""));

          if (categoriesFilter.includes(catId) || conf < minConfidence)
            child.hide();
          else child.show();
        });
      });
    });

    updateButtons();
  }

  // Update every button status and style
  function updateButtons() {
    // Update showAllCategories button
    (document.getElementById("toggle-items") as HTMLInputElement).checked =
      categoriesFilter.length == 0;

    // Update showAllViews button
    if (Object.keys(features.views).length > 1) {
      (document.getElementById("toggle-views") as HTMLInputElement).checked =
        viewsFilter.length == 0;

      // Update every view button
      Object.keys(features.views).forEach((view) => {
        (document.getElementById(`view-${view}`) as HTMLInputElement).checked =
          !viewsFilter.includes(view);
      });
    }

    // Update all category buttons color according to their corresponding category visibility status
    features.categoryStats.forEach((cat) => {
      let categoryButton = document.getElementById(`cat-${cat.id}`);
      if (categoriesFilter.includes(cat.id))
        categoryButton.classList.add("grayscale"); // Colorful if visible
      else categoryButton.classList.remove("grayscale"); // Gray if hidden
    });
  }

  // Draws the image and all its items.
  function draw() {
    KonvaUtils.clearCanvas(stage); // Clear previous drawings

    // Calculate max dims for every image in the grid
    let maxWidth = window.innerWidth / gridSize.cols;
    let maxHeight = window.innerHeight / gridSize.rows;

    // Set first image position in the grid
    let position = {
      col: 0,
      row: 0,
    };

    // For each view
    for (const [name, view] of Object.entries(features.views)) {
      let layer;
      for (const child of stage.children)
        if (name === child.name()) layer = child; // Get the layer corresponding to the view

      // Create groups for image, bboxes, and masks
      let imageGroup = new Konva.Group({ name: "images" });
      let boundingBoxesGroup = new Konva.Group({ name: "boxes" });
      let masksGroup = new Konva.Group({ name: "masks" });
      let tooltipsGroup = new Konva.Group({ name: "tooltips" });

      const image = new Image();
      image.onload = () => {
        // If the image is too big, downscale it, else leave it normal
        let scaleByWidth = maxWidth / image.width;
        let scaleByHeight = maxHeight / image.height;
        let scale = Math.min(scaleByWidth, scaleByHeight);

        // Calculate image dimensions after scaling
        let imgSize = {
          width: image.width * scale,
          height: image.height * scale,
        };

        // Calculate offset to center image
        let offset = {
          x: maxWidth * position.col + (maxWidth - image.width * scale) / 2,
          y: maxHeight * position.row + (maxHeight - image.height * scale) / 2,
        };

        KonvaUtils.drawImage(imageGroup, image, offset, scale); // Draw the image

        // For each item
        for (let i = 0; i < view.objects.boundingBox.length; ++i) {
          let category = view.objects.category[i];
          let id = `category-${category.id}-`;

          // Bounding box & confidence tooltip
          if (view.objects.boundingBox[i]) {
            let bbox = view.objects.boundingBox[i];

            if (bbox.width != 0 && bbox.height != 0) {
              let bboxCoords = KonvaUtils.calculateBBoxCoordinates(
                bbox,
                imgSize,
                offset
              );

              // Draw bounding box
              KonvaUtils.drawBoundingBox(
                id + (bbox.is_predict ? bbox.confidence : 1),
                boundingBoxesGroup,
                bboxCoords,
                categoryColor(category.id),
                bbox.is_predict
              );

              // Draw tooltip
              KonvaUtils.drawTooltip(
                id + (bbox.is_predict ? bbox.confidence : 1),
                tooltipsGroup,
                category.name +
                  (bbox.is_predict ? " " + bbox.confidence.toString() : ""),
                { x: bboxCoords.x, y: bboxCoords.y },
                categoryColor(category.id)
              );
            }
          }

          // Mask
          if (view.objects.segmentation[i]) {
            let mask_rle = view.objects.segmentation[i];
            //const mask_rle = itemDetails.views.image.objects.segmentation[i];
            const rle = mask_rle["counts"];
            const size = mask_rle["size"];
            const maskPolygons = generatePolygonSegments(rle, size[0]);
            const masksSVG = convertSegmentsToSVG(maskPolygons);

            /*
            let maskCoords = KonvaUtils.calculateMaskCoordinates(
              masksSVG,
              imgSize,
              offset
            );
            */
            console.log("SQ", offset, imgSize, scale);
            // Draw mask
            /*
            KonvaUtils.drawMask(
              id + 1,
              offset.x,
              offset.y,
              {x: scale, y: scale},
              masksGroup,
              masksSVG,
              categoryColor(category.id)
            );
            */
          }
        }

        // Add the different groups to the layer
        layer.add(imageGroup);
        layer.add(boundingBoxesGroup);
        layer.add(tooltipsGroup);
        layer.add(masksGroup);

        // Add a label to the layer and draw it
        KonvaUtils.drawLabel(layer, name, offset);
        stage.draw();

        // Calculate next grid position
        if (position.col == gridSize.cols - 1) {
          position.col = 0;
          position.row++;
        } else position.col++;

        updateElementsVisibility(); // Refresh elements
      };

      image.src = view.image; // Set image source
    }
  }

  onMount(() => {
    // Create canvas
    stage = new Konva.Stage({
      height: window.innerHeight,
      width: window.innerWidth,
      container: "canvas",
    });

    // Set up a layer for each view
    Object.keys(features.views).forEach((k) => {
      let layer = new Konva.Layer({ name: k, draggable: true }); // Create a layer

      // Add handler for selecting an image
      layer.on("dblclick", layer.moveToTop);

      // Change mouse cursor on hover
      layer.on("mouseenter", () => (stage.container().style.cursor = "move"));
      layer.on(
        "mouseleave",
        () => (stage.container().style.cursor = "default")
      );

      stage.add(layer); // Add layer to canvas stage
    });

    // Add handler for zooming
    stage.on("wheel", (e) => {
      e.evt.preventDefault(); // Prevent default scrolling

      let direction = e.evt.deltaY < 0 ? 1 : -1; // Get zoom direction

      // When we zoom on trackpad, e.evt.ctrlKey is true
      // In that case lets revert direction.
      if (e.evt.ctrlKey) direction = -direction;

      KonvaUtils.zoom(stage, direction);
    });
  });

  beforeUpdate(() => {
    // If the image has changed
    if (features.id != oldID) {
      categoryColor = Utils.getColor(features.categoryStats.map((it) => it.id)); // Define a color map for each category id

      // Calculate new grid size
      let viewsCount = Object.keys(features.views).length;
      gridSize.cols = Math.ceil(Math.sqrt(viewsCount));
      gridSize.rows = Math.ceil(viewsCount / gridSize.cols);
    }
  });

  afterUpdate(() => {
    // If the image has changed
    if (features.id != oldID) {
      oldID = features.id; // Update image id
      draw(); // Draw image
    }
  });
</script>

<!-- Konva canvas -->
<div
  class="absolute top-0 left-0 w-full h-full bg-white dark:bg-zinc-800"
  id="canvas"
/>

<!-- Toolbox -->
<div
  class="absolute w-64 top-1/2 -translate-y-1/2 right-6 py-2 px-4 flex flex-col bg-white text-zinc-900 border rounded-lg shadow
  dark:text-zinc-300 dark:bg-zinc-900 dark:border-zinc-500"
>
  <!-- Data -->
  <div class="flex flex-col">
    <span
      class="mb-2 self-center text-sm text-zinc-500 font-medium uppercase dark:text-zinc-400"
    >
      Data
    </span>
    <div class="flex flex-col">
      {#if features.id}
        <div>
          <span class="font-bold"> Id : </span>
          <span> {features.id} </span>
        </div>
      {/if}
      {#if features.filename}
        <div>
          <span class="font-bold"> Filename : </span>
          <span> {features.filename} </span>
        </div>
      {/if}
      {#if features.width && features.height}
        <div>
          <span class="font-bold"> Size : </span>
          <span> {features.width}x{features.height}px</span>
        </div>
      {/if}
    </div>
  </div>

  <!-- Tools -->
  <div class="mt-2 pt-2 flex flex-col border-t dark:border-zinc-700">
    <span
      class="mb-2 self-center text-center text-sm text-zinc-500 font-medium uppercase dark:text-zinc-400"
    >
      Tools
    </span>
    <!-- Items -->
    <!-- Controls -->
    <div class="mb-2 flex items-center space-x-2">
      <!-- Show all items checkbox -->
      <input
        class="cursor-pointer checked:accent-rose-500"
        type="checkbox"
        id="toggle-items"
        checked
        on:change={toggleAllCategoriesVisibility}
      />
      <label class="font-bold cursor-pointer" for="toggle-items">
        Show all items
      </label>
    </div>

    <div class="mb-2 flex items-center space-x-2">
      <!-- Show boxes checkbox -->
      <input
        class="cursor-pointer checked:accent-rose-500"
        type="checkbox"
        id="toggle-boxes"
        bind:checked={showBoundingBoxes}
        on:change={updateElementsVisibility}
      />
      <label class="font-bold cursor-pointer" for="toggle-boxes">
        Show boxes
      </label>
    </div>

    <!-- Opacity slider -->
    <label class="font-bold mt-2 mb-1" for="slider">
      Mask opacity : {maskOpacity * 100}%
    </label>
    <input
      class="cursor-pointer"
      type="range"
      id="slider"
      min="0"
      max="1"
      step="0.1"
      bind:value={maskOpacity}
      on:input={updateMasksOpacity}
    />

    <!-- Confidence filter -->
    <label class="font-bold mt-2 mb-1" for="slider">
      Minimum confidence : {minConfidence}
    </label>
    <input
      class="cursor-pointer"
      type="range"
      id="slider"
      min="0"
      max="1"
      step="0.01"
      bind:value={minConfidence}
      on:input={updateElementsVisibility}
    />
  </div>

  <!-- Item Categories -->
  <span class="font-bold mb-2 mt-2"> Categories : </span>
  <div class="flex flex-wrap">
    {#if categoryColor != null}
      {#each features.categoryStats as category}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- Toggle Category Button -->
        <button
          class="relative px-1 mb-2 mr-4 rounded-lg text-sm text-zinc-900 font-bold border-2 border-transparent
          hover:border-rose-500"
          style="background-color: {categoryColor(category.id)};"
          id="cat-{category.id}"
          on:click={() => toggleCategoryVisibility(category.id)}
        >
          {category.name}
          <!-- Category count index -->
          {#if category.count != 1}
            <span
              class="block absolute -right-3 -top-2 h-fit px-1 text-xs rounded-full bg-rose-500 text-white font-bold"
            >
              {category.count}
            </span>
          {/if}
        </button>
      {/each}
    {/if}
  </div>

  <!-- Views -->
  {#if Object.keys(features.views).length != 1}
    <div class="mt-2 pt-2 flex flex-col border-t dark:border-zinc-700">
      <span
        class="mb-2 self-center text-center text-sm text-zinc-500 font-medium uppercase dark:text-zinc-400"
      >
        Views
      </span>
      <!-- Controls -->
      <div class="mb-2 flex items-center space-x-2">
        <!-- Show all views checkbox -->
        <input
          class="cursor-pointer checked:accent-rose-500"
          type="checkbox"
          id="toggle-views"
          checked
          on:change={toggleAllViewsVisibility}
        />
        <label class="font-bold cursor-pointer" for="toggle-views">
          Show all views
        </label>
      </div>
    </div>

    <span class="font-bold"> Views : </span>
    <div class="flex flex-col">
      {#if categoryColor != null}
        {#each Object.keys(features.views) as view}
          <div class="ml-1 flex items-center space-x-2">
            <!-- Show all views checkbox -->
            <input
              class="cursor-pointer checked:accent-rose-500"
              type="checkbox"
              id="view-{view}"
              checked
              on:change={() => toggleViewVisibility(view)}
            />
            <label class="font-medium cursor-pointer" for="view-{view}">
              {view}
            </label>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>
