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
  import type { AnnotationsLabels } from "../../../../components/canvas2d/src/interfaces";
  import * as Utils from "@pixano/core/src/utils";

  // Exports
  export let features = null;
  export let annotations: Array<AnnotationsLabels>;

  const dispatch = createEventDispatcher();

  let oldID: number;

  let activeTab = "labels";

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
  }

  onMount(() => {
    console.log("AnnInspector - onMount (anns):", annotations);
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

<div
  class="absolute h-4/6 w-72 top-1/2 -translate-y-1/2 right-6 border rounded-lg shadow-xl
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500"
>
  <div class="h-12 fixed w-full flex items-center justify-evenly">
    <span
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase rounded-t-lg
      text-zinc-500 dark:text-zinc-300
      hover:bg-zinc-100 dark:hover:bg-zinc-700
      {activeTab == 'labels'
        ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
        : 'border-zinc-300 dark:border-zinc-500'}"
    >
      Labels
    </span>
  </div>
  <div class="pt-12 flex flex-col h-full">
    <div
      class="h-full px-4 overflow-auto {activeTab == 'labels' ? '' : 'hidden'}"
    >
      <!-- Details -->
      {#if features.filename || (features.width && features.height)}
        <div class="flex flex-col py-4">
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
      {/if}
      <!-- Controls -->
      <div class="flex flex-col py-4">
        <div class="mb-2 flex items-center space-x-2">
          <!-- Show all items checkbox -->
          <input
            class="cursor-pointer checked:accent-rose-500 dark:checked:accent-rose-600"
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
            class="cursor-pointer checked:accent-rose-500 dark:checked:accent-rose-600"
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
      <div class="flex flex-wrap py-4">
        {#if categoryColor != null}
          {#each features.categoryStats as category}
            <!-- Toggle Category Button -->
            <button
              class="relative px-1 mb-2 mr-4 rounded-lg text-sm font-bold border-2 border-transparent
              text-zinc-800 hover:border-rose-500"
              style="background-color: {categoryColor(category.id)};"
              id="cat-{category.id}"
              on:click={() => toggleCategoryVisibility(category.name)}
            >
              {category.name}
              <!-- Category count index -->
              {#if category.count != 1}
                <span
                  class="block absolute -right-3 -top-2 h-fit px-1 text-xs rounded-full bg-rose-500 dark:bg-rose-600 text-zinc-50 font-bold"
                >
                  {category.count}
                </span>
              {/if}
            </button>
          {/each}
        {/if}
      </div>
    </div>
  </div>
</div>
