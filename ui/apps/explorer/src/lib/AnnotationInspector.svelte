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
  import { onMount, beforeUpdate } from "svelte";
  import { createEventDispatcher } from "svelte";
  import type { AnnotationsLabels } from "../../../../components/Canvas2D/src/interfaces";
  import * as Utils from "@pixano/core/src/utils";

  // Exports
  export let features = null;
  export let annotations: Array<AnnotationsLabels>;

  const dispatch = createEventDispatcher();

  let oldID: number;

  // Function that maps an id to a color
  let categoryColor = null;

  // Multiview image grid
  let gridSize = {
    rows: 0,
    cols: 0,
  };

  // Filters
  let maskOpacity: number = 1.0;
  let minConfidence: number = 0.5;

  let viewsFilter: Array<string> = [];

  function updateConfidenceFilterEvent(event) {
    updateConfidenceFilter(parseFloat(event.target.value));
  }

  function updateConfidenceFilter(confidence) {
    for (let cat of annotations) {
      for (let item of cat.items) {
        if (item.confidence) {
          item.visible = item.confidence >= confidence;
        }
      }
    }
    dispatch("toggleCatVis");
  }

  // Change every mask opacity to match the desired value.
  function updateMasksOpacity() {
    for (let cat of annotations) {
      for (let item of cat.items) {
        item.opacity = maskOpacity;
      }
    }
    dispatch("changeMaskOpacity", maskOpacity);
  }

  function toggleAllBBoxVisbility(event) {
    dispatch("toggleAllBBoxVis", event.target.checked);
  }

  /**
   * Toggle on/off a category visibility.
   * @param category category to show/hide
   */
  function toggleCategoryVisibility(category: string) {
    let allVisible = true;
    for (let cat of annotations) {
      if (cat.category_name === category) {
        cat.visible = !cat.visible;
        let categoryButton = document.getElementById(`cat-${cat.category_id}`);
        if (cat.visible) {
          categoryButton.classList.remove("grayscale");
        } else {
          categoryButton.classList.add("grayscale");
        }
        for (let item of cat.items) {
          item.visible = cat.visible;
        }
      }
      allVisible = allVisible && cat.visible;
    }
    // Update showAllCategories button
    let allVis_elem = document.getElementById(
      "toggle-items"
    ) as HTMLInputElement;
    allVis_elem.checked = allVisible;

    dispatch("toggleCatVis");
    updateButtons();
  }

  // Show or hide every category.
  function toggleAllCategoriesVisibility(event) {
    for (let cat of annotations) {
      cat.visible = event.target.checked;
      for (let item of cat.items) {
        let categoryButton = document.getElementById(`cat-${cat.category_id}`);
        if (cat.visible) {
          categoryButton.classList.remove("grayscale");
        } else {
          categoryButton.classList.add("grayscale");
        }
        if (item.visible !== cat.visible) {
          item.visible = cat.visible;
        }
      }
    }
    dispatch("toggleCatVis");
    updateButtons();
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
    console.log("TODO: update visibility");
    /*
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
    */
    updateButtons();
  }

  // Update every button status and style
  function updateButtons() {
    // Update showAllCategories button
    /*
    (document.getElementById("toggle-items") as HTMLInputElement).checked =
      categoriesFilter.length == 0;
    */
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
    /*
    features.categoryStats.forEach((cat) => {
      let categoryButton = document.getElementById(`cat-${cat.id}`);
      if (categoriesFilter.includes(cat.id))
        categoryButton.classList.add("grayscale"); // Colorful if visible
      else categoryButton.classList.remove("grayscale"); // Gray if hidden
    });
    */
  }

  onMount(() => {
    console.log("AnnInspector - onMount (anns):", annotations);
    console.log("AnnInspector - onMount (feats):", features);
    updateConfidenceFilter(minConfidence);
  });

  beforeUpdate(() => {
    // If the image has changed
    if (features.id != oldID) {
      categoryColor = Utils.getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id

      // Calculate new grid size
      let viewsCount = Object.keys(features.views).length;
      gridSize.cols = Math.ceil(Math.sqrt(viewsCount));
      gridSize.rows = Math.ceil(viewsCount / gridSize.cols);
    }
  });
</script>

<!-- Toolbox -->
<div
  class="absolute w-72 top-1/2 -translate-y-1/2 right-6 py-2 px-4 flex flex-col bg-white text-zinc-900 border rounded-lg shadow-xl
    dark:text-zinc-300 dark:bg-zinc-900 dark:border-zinc-500"
>
  <!-- Data -->
  <div class="flex flex-col">
    <span
      class="mb-2 self-center text-sm text-zinc-500 font-bold uppercase dark:text-zinc-400"
    >
      Data
    </span>
    <div class="flex flex-col">
      {#if features.id}
        <div>
          <span class="font-bold"> id : </span>
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
      class="mb-2 self-center text-center text-sm text-zinc-500 font-bold uppercase dark:text-zinc-400"
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
        Show all annotations
      </label>
    </div>

    <div class="mb-2 flex items-center space-x-2">
      <!-- Show boxes checkbox -->
      <input
        class="cursor-pointer checked:accent-rose-500"
        type="checkbox"
        id="toggle-boxes"
        checked
        on:change={toggleAllBBoxVisbility}
      />
      <label class="font-bold cursor-pointer" for="toggle-boxes">
        Show bounding boxes
      </label>
    </div>

    <!-- Opacity slider -->
    <label class="font-bold mt-2 mb-1" for="slider">
      Mask opacity: {maskOpacity * 100}%
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
      Confidence threshold: {Math.round(minConfidence * 100)}%
    </label>
    <input
      class="cursor-pointer"
      type="range"
      id="slider"
      min="0"
      max="1"
      step="0.01"
      bind:value={minConfidence}
      on:input={updateConfidenceFilterEvent}
    />
  </div>

  <!-- Item Categories -->
  <span class="font-bold mb-2 mt-2"> Labels: </span>
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
          on:click={() => toggleCategoryVisibility(category.name)}
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
