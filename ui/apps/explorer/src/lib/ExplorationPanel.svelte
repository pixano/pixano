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

  import { icons, utils } from "@pixano/core";

  import type {
    CategoryLabels,
    ItemData,
    ItemLabels,
    Label,
    SourceLabels,
    ViewLabels,
  } from "@pixano/core";

  // Exports
  export let selectedItem: ItemData;
  export let annotations: ItemLabels;
  export let classes;

  const dispatch = createEventDispatcher();

  let activeTab = "labels";
  let categoryColor = null;
  let allAnnHidden = false;
  let allBBoxHidden = false;
  let viewsEmpty = true;

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
              updateLabelVisibility(label, label.confidence >= minConfidence);
            }
          }
        }
      }
    }
  }

  function updateLabelVisibility(label: Label, visibility: boolean) {
    if (label.confidence) {
      label.visible = visibility && label.confidence >= minConfidence;
    } else {
      label.visible = visibility;
    }
    dispatch("labelVisibility", label);
  }

  function handleLabelVisibility(
    view: ViewLabels,
    source: SourceLabels,
    category: CategoryLabels,
    label: Label
  ) {
    // Toggle visibility
    label.visible = !label.visible;
    // Toggle parents if needed
    if (label.visible && !category.visible) {
      category.visible = true;
    }
    if (label.visible && !source.visible) {
      source.visible = true;
    }
    if (label.visible && !view.visible) {
      view.visible = true;
    }
    // Dispatch label visibility change
    dispatch("labelVisibility", label);
  }

  function handleCategoryVisibility(
    view: ViewLabels,
    source: SourceLabels,
    category: CategoryLabels
  ) {
    // Toggle visibility
    category.visible = !category.visible;
    // Toggle parents if needed
    if (category.visible && !source.visible) {
      source.visible = true;
    }
    if (category.visible && !view.visible) {
      view.visible = true;
    }
    // Dispatch label visibility change
    for (let label of Object.values(category.labels)) {
      label.visible = category.visible;
      dispatch("labelVisibility", label);
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
              updateLabelVisibility(label, !label.visible);
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
              updateLabelVisibility(label, !label.visible);
            }
          }
        }
      }
    }
  }

  onMount(() => {
    handleConfidenceFilter();
  });

  beforeUpdate(() => {
    if (annotations) {
      annotations = annotations;
      for (const viewLabels of Object.values(annotations)) {
        if (viewLabels.numLabels > 0) viewsEmpty = false;
      }
      categoryColor = utils.getColor(classes.map((cat) => classes.id)); // Define a color map for each category id
    }
  });
</script>

<div
  class="absolute h-4/6 w-72 top-1/2 -translate-y-1/2 right-6 border rounded-lg shadow-xl
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500
    text-zinc-500 dark:text-zinc-300"
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
    <div class="h-full overflow-auto {activeTab == 'labels' ? '' : 'hidden'}">
      {#if viewsEmpty}
        <p class="py-4 text-center font-bold italic">No annotations yet.</p>
      {:else}
        <div
          class="px-4 border-b-2
    border-zinc-300 dark:border-zinc-500"
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
        </div>
        {#each Object.entries(annotations) as [viewId, view]}
          {#if Object.keys(annotations).length > 1}
            <div
              class="px-3 py-5 flex items-center space-x-1 select-none border-b-2
            border-zinc-300 dark:border-zinc-500
            {view['opened'] ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
            >
              <button on:click={() => handleViewVisibility(view)}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-6 w-6"
                >
                  <title>{view["visible"] ? "Hide" : "Show"}</title>
                  <path
                    d={view["visible"] ? icons.svg_hide : icons.svg_show}
                    fill="currentcolor"
                  />
                </svg>
              </button>
              <button
                class="flex grow items-center space-x-1 text-left"
                on:click={() => (view["opened"] = !view["opened"])}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-6 w-6"
                >
                  <title>{view["opened"] ? "Close" : "Open"}</title>
                  <path
                    d={view["opened"] ? icons.svg_close : icons.svg_open}
                    fill="currentcolor"
                  />
                </svg>

                <span class="grow ml-3 font-bold">
                  {viewId}
                </span>
                <span
                  class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
                  title="{view.numLabels} labels"
                >
                  {view.numLabels}
                </span>
              </button>
            </div>
          {/if}
          {#each Object.entries(view.sources) as [sourceId, source]}
            {#if source.numLabels}
              <div
                class="px-3 py-5 flex items-center space-x-1 select-none border-b-2
            border-zinc-300 dark:border-zinc-500
            {view['opened'] ? 'flex' : 'hidden'}
            {Object.keys(annotations).length > 1 ? 'pl-6' : ''}
            {source['opened'] ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
              >
                <button on:click={() => handleSourceVisibility(view, source)}>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    height="48"
                    viewBox="0 -960 960 960"
                    width="48"
                    class="h-6 w-6"
                  >
                    <title>{source["visible"] ? "Hide" : "Show"}</title>
                    <path
                      d={source["visible"] ? icons.svg_hide : icons.svg_show}
                      fill="currentcolor"
                    />
                  </svg>
                </button>
                <button
                  class="flex items-center space-x-1 text-left"
                  on:click={() => (source["opened"] = !source["opened"])}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    height="48"
                    viewBox="0 -960 960 960"
                    width="48"
                    class="h-6 w-6"
                  >
                    <title>{source["opened"] ? "Close" : "Open"}</title>
                    <path
                      d={source["opened"] ? icons.svg_close : icons.svg_open}
                      fill="currentcolor"
                    />
                  </svg>

                  <span class="relative pl-3 grow truncate" title={sourceId}>
                    {sourceId}
                  </span>
                  <span
                    class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
                    title="{source.numLabels} labels"
                  >
                    {source.numLabels}
                  </span>
                </button>
              </div>
              {#each Object.entries(source.categories) as [categoryName, category]}
                <div
                  class="px-3 py-5 flex items-center space-x-1 select-none border-b-2
                border-zinc-300 dark:border-zinc-500
                {view['opened'] && source['opened'] ? 'flex' : 'hidden'}
                {Object.keys(annotations).length > 1 ? 'pl-9' : 'pl-6'}
                {category['opened'] ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
                >
                  <button
                    on:click={() =>
                      handleCategoryVisibility(view, source, category)}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6"
                    >
                      <title>{category["visible"] ? "Hide" : "Show"}</title>
                      <path
                        d={category["visible"]
                          ? icons.svg_hide
                          : icons.svg_show}
                        fill="currentcolor"
                      />
                    </svg>
                  </button>
                  <button
                    class="flex grow items-center space-x-1 text-left"
                    on:click={() => (category["opened"] = !category["opened"])}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6"
                    >
                      <title>{category["opened"] ? "Close" : "Open"}</title>
                      <path
                        d={category["opened"]
                          ? icons.svg_close
                          : icons.svg_open}
                        fill="currentcolor"
                      />
                    </svg>
                    <span class="grow ml-3 font-bold text-zinc-800">
                      <button
                        class="relative px-1 rounded-lg text-sm"
                        style="background-color: {categoryColor(category.id)};"
                      >
                        {category.name}
                      </button>
                    </span>
                    <span
                      class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
                      title="{Object.keys(category.labels).length} labels"
                    >
                      {Object.keys(category.labels).length}
                    </span>
                  </button>
                </div>
                <div class="{category['opened'] ? 'flex' : 'hidden'} flex-col">
                  {#each Object.entries(category.labels) as [labelId, label]}
                    <div
                      class="p-3 pl-12 flex items-center space-x-1 border-b-2
                    {Object.keys(annotations).length > 1 ? 'pl-12' : 'pl-9'}
                    border-zinc-300 dark:border-zinc-500"
                    >
                      <button
                        on:click={() =>
                          handleLabelVisibility(view, source, category, label)}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          height="48"
                          viewBox="0 -960 960 960"
                          width="48"
                          class="h-5 w-5"
                        >
                          <title>
                            {(category.visible && label.visible) ||
                            label.visible
                              ? "Hide"
                              : "Show"}
                          </title>
                          <path
                            d={(category.visible && label.visible) ||
                            label.visible
                              ? icons.svg_hide
                              : icons.svg_show}
                            fill="currentcolor"
                          />
                        </svg>
                      </button>
                      <span
                        class="relative pl-3 text-sm grow truncate"
                        title={label.id}
                      >
                        {label.id}
                      </span>
                    </div>
                  {/each}
                </div>
              {/each}
            {/if}
          {/each}
        {/each}
      {/if}
    </div>
  </div>
</div>
