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
  import { beforeUpdate, createEventDispatcher, onMount } from "svelte";

  import { utils } from "@pixano/core";

  import type { AnnotationCategory } from "@pixano/core";

  // Exports
  export let features = null;
  export let annotations: Array<AnnotationCategory>;

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

  function handleConfidenceFilter(event) {
    updateConfidenceFilter(parseFloat(event.target.value));
  }

  function updateConfidenceFilter(confidence) {
    for (let category of annotations) {
      for (let item of category.labels) {
        if (item.confidence) {
          item.visible = item.confidence >= confidence;
        }
      }
    }
    dispatch("categoryVisibility");
  }

  // Change every mask opacity to match the desired value.
  function handleMaskOpacity() {
    for (let category of annotations) {
      for (let item of category.labels) {
        item.opacity = maskOpacity;
      }
    }
    dispatch("maskOpacity", maskOpacity);
  }

  function handleBboxesVisibility(event) {
    dispatch("bboxesVisibility", event.target.checked);
  }

  /**
   * Toggle on/off a category visibility.
   * @param category category to show/hide
   */
  function handleCategoryVisibility(category_name: string) {
    let allVisible = true;
    for (let category of annotations) {
      if (category.name === category_name) {
        category.visible = !category.visible;
        let categoryButton = document.getElementById(`cat-${category.id}`);
        if (category.visible) {
          categoryButton.classList.remove("grayscale");
        } else {
          categoryButton.classList.add("grayscale");
        }
        for (let label of category.labels) {
          label.visible = category.visible;
        }
      }
      allVisible = allVisible && category.visible;
    }
    // Update showAllCategories button
    let allVis_elem = document.getElementById(
      "toggle-items"
    ) as HTMLInputElement;
    allVis_elem.checked = allVisible;

    dispatch("categoryVisibility");
  }

  // Show or hide every category.
  function handleAllCategoriesVisibility(event) {
    for (let category of annotations) {
      category.visible = event.target.checked;
      for (let label of category.labels) {
        let categoryButton = document.getElementById(`cat-${category.id}`);
        if (category.visible) {
          categoryButton.classList.remove("grayscale");
        } else {
          categoryButton.classList.add("grayscale");
        }
        if (label.visible !== category.visible) {
          label.visible = category.visible;
        }
      }
    }
    dispatch("categoryVisibility");
  }

  onMount(() => {
    updateConfidenceFilter(minConfidence);
  });

  beforeUpdate(() => {
    // If the image has changed
    if (features.id != oldID) {
      categoryColor = utils.getColor(annotations.map((cat) => cat.id)); // Define a color map for each category id

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
            on:change={handleAllCategoriesVisibility}
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
            on:change={handleBboxesVisibility}
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
          on:input={handleMaskOpacity}
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
          on:input={handleConfidenceFilter}
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
              on:click={() => handleCategoryVisibility(category.name)}
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
