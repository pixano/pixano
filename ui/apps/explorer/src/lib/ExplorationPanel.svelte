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

  import type {
    ItemData,
    ItemLabels,
    Label,
    SourceLabels,
    ViewLabels,
  } from "@pixano/core";

  // Exports
  export let selectedItem: ItemData;
  export let annotations: ItemLabels;

  const dispatch = createEventDispatcher();

  let currentID: string;
  let activeTab = "labels";
  let categoryColor = null;
  let allAnnHidden = false;
  let allBBoxHidden = false;

  // Multiview image grid
  let gridSize = {
    rows: 0,
    cols: 0,
  };

  // Filters
  let maskOpacity: number = 1.0;
  let minConfidence: number = 0.5;

  function handleConfidenceFilter() {
    for (let view of Object.values(annotations)) {
      for (let source of Object.values(view.sources)) {
        for (let category of Object.values(source.categories)) {
          for (let label of Object.values(category.labels)) {
            if (
              label.confidence &&
              !allAnnHidden &&
              ((label.type === "bbox" && !allBBoxHidden) ||
                label.type === "mask")
            ) {
              handleLabelVisibility(label, label.confidence >= minConfidence);
            }
          }
        }
      }
    }
  }

  function handleLabelVisibility(label: Label, visibility: boolean) {
    if (label.confidence) {
      label.visible = visibility && label.confidence >= minConfidence;
    } else {
      label.visible = visibility;
    }
    dispatch("labelVisibility", label);
  }

  function handleCategoryVisibility(categoryName: string) {
    // Toggle visibility
    for (let view of Object.values(annotations)) {
      for (let source of Object.values(view.sources)) {
        for (let category of Object.values(source.categories)) {
          if (category.name === categoryName) {
            category.visible = !category.visible;
            for (let label of Object.values(category.labels)) {
              handleLabelVisibility(label, category.visible);
            }
          }
        }
      }
    }
  }

  function handleSourceVisibility(view: ViewLabels, source: SourceLabels) {
    // Toggle visibility
    source.visible = !source.visible;
    // Toggle parents if needed
    if (source.visible && !view.visible) {
      view.visible = true;
    }
    // Dispatch label visibility change
    for (let category of Object.values(source.categories)) {
      category.visible = source.visible;
      for (let label of Object.values(category.labels)) {
        label.visible = source.visible;
        dispatch("labelVisibility", label);
      }
    }
  }

  function handleViewVisibility(view: ViewLabels) {
    // Toggle visibility
    view.visible = !view.visible;
    // Dispatch label visibility change
    for (let source of Object.values(view.sources)) {
      source.visible = view.visible;
      for (let category of Object.values(source.categories)) {
        category.visible = view.visible;
        for (let label of Object.values(category.labels)) {
          label.visible = view.visible;
          dispatch("labelVisibility", label);
        }
      }
    }
  }

  function handleAllVisibility() {
    allAnnHidden = !allAnnHidden;
    for (let view of Object.values(annotations)) {
      // Toggle visibility
      view.visible = !view.visible;
      // Dispatch label visibility change
      for (let source of Object.values(view.sources)) {
        source.visible = view.visible;
        for (let category of Object.values(source.categories)) {
          category.visible = view.visible;
          for (let label of Object.values(category.labels)) {
            if (
              (label.type === "bbox" && !allBBoxHidden) ||
              label.type === "mask"
            ) {
              handleLabelVisibility(label, !label.visible);
            }
          }
        }
      }
    }
  }

  // Change every mask opacity to match the desired value.
  function handleMaskOpacity() {
    for (let view of Object.values(annotations)) {
      for (let source of Object.values(view.sources)) {
        for (let category of Object.values(source.categories)) {
          for (let label of Object.values(category.labels)) {
            if (label.type === "mask") {
              label.opacity = maskOpacity;
              dispatch("labelVisibility", label);
            }
          }
        }
      }
    }
  }

  function handleBboxesVisibility() {
    allBBoxHidden = !allBBoxHidden;
    for (let view of Object.values(annotations)) {
      for (let source of Object.values(view.sources)) {
        for (let category of Object.values(source.categories)) {
          for (let label of Object.values(category.labels)) {
            if (label.type === "bbox" && !allAnnHidden) {
              handleLabelVisibility(label, !label.visible);
            }
          }
        }
      }
    }
  }

  onMount(() => {
    console.log("ExplorationPanel.onMount");
    console.log(selectedItem.catStats);
    handleConfidenceFilter();
  });

  beforeUpdate(() => {
    console.log("ExplorationPanel.beforeUpdate");
    // If the image has changed
    if (currentID !== selectedItem.id) {
      // Calculate new grid size
      let viewsCount = Object.keys(selectedItem.views).length;
      gridSize.cols = Math.ceil(Math.sqrt(viewsCount));
      gridSize.rows = Math.ceil(viewsCount / gridSize.cols);
      currentID = selectedItem.id;
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
      {#if selectedItem.filename || (selectedItem.width && selectedItem.height)}
        <div class="flex flex-col py-4">
          {#if selectedItem.filename}
            <div>
              <span class="font-bold"> Filename : </span>
              <span> {selectedItem.filename} </span>
            </div>
          {/if}
          {#if selectedItem.width && selectedItem.height}
            <div>
              <span class="font-bold"> Size : </span>
              <span> {selectedItem.width}x{selectedItem.height}px</span>
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
            on:change={handleAllVisibility}
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
          {#each selectedItem.catStats as category}
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
