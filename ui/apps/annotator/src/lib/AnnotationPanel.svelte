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

  import { icons } from "@pixano/core";

  import type {
    CategoryLabels,
    Dataset,
    DatasetItem,
    ItemData,
    ItemLabels,
    Label,
    SourceLabels,
    ViewLabels,
  } from "@pixano/core";

  // Exports
  export let selectedItem: ItemData;
  export let selectedDataset: Dataset;
  export let annotations: ItemLabels;
  export let currentPage: number;
  export let labelColors;
  export let maskOpacity: number;
  export let bboxOpacity: number;
  export let confidenceThreshold: number;

  const dispatch = createEventDispatcher();

  let activeTab = "labels"; //"dataset";
  let noLabels = true;

  // Change selected image
  function handleSelectItem(item: DatasetItem) {
    dispatch("selectItem", item);
  }

  function handleDeleteLabel(label: Label) {
    dispatch("deleteLabel", label);
  }

  function handleLabelVisibility(
    source: SourceLabels,
    view: ViewLabels,
    category: CategoryLabels,
    label: Label,
    visibility: boolean
  ) {
    // Toggle visibility
    label.visible = visibility;
    dispatch("labelVisibility", label);
    // Toggle parents if needed
    if (label.visible && !category.visible) {
      category.visible = true;
    }
    if (label.visible && !view.visible) {
      view.visible = true;
    }
    if (label.visible && !source.visible) {
      source.visible = true;
    }
  }

  function handleCategoryVisibility(
    source: SourceLabels,
    view: ViewLabels,
    category: CategoryLabels,
    visibility: boolean
  ) {
    // Toggle visibility
    category.visible = visibility;
    // Toggle parents if needed
    if (category.visible && !view.visible) {
      view.visible = true;
    }
    if (category.visible && !source.visible) {
      source.visible = true;
    }
    // Toggle children
    for (let label of Object.values(category.labels)) {
      label.visible = category.visible;
      dispatch("labelVisibility", label);
    }
  }

  function handleViewVisibility(
    source: SourceLabels,
    view: ViewLabels,
    visibility: boolean
  ) {
    // Toggle visibility
    view.visible = visibility;
    // Toggle parents if needed
    if (view.visible && !source.visible) {
      source.visible = true;
    }
    // Toggle children
    for (let category of Object.values(view.categories)) {
      category.visible = view.visible;
      for (let label of Object.values(category.labels)) {
        label.visible = view.visible;
        dispatch("labelVisibility", label);
      }
    }
  }

  function handleSourceVisibility(source: SourceLabels, visibility: boolean) {
    // Toggle visibility
    source.visible = visibility;
    // Toggle children
    for (let view of Object.values(source.views)) {
      view.visible = source.visible;
      for (let category of Object.values(view.categories)) {
        category.visible = source.visible;
        for (let label of Object.values(category.labels)) {
          label.visible = source.visible;
          dispatch("labelVisibility", label);
        }
      }
    }
  }

  async function handleDatasetScroll(event) {
    if (currentPage * 100 < selectedDataset.page.total) {
      const totalContentHeight =
        event.target.scrollHeight - event.target.clientHeight;
      const offset10percent = Math.ceil(totalContentHeight * 0.1);
      if (event.target.scrollTop > totalContentHeight - offset10percent) {
        dispatch("loadNextPage");
      }
    }
  }

  onMount(() => {
    console.log("AnnotationPanel.onMount");
    dispatch("labelFilters");
  });

  afterUpdate(() => {
    console.log("AnnotationPanel.afterUpdate");
    if (annotations) {
      annotations = annotations;
      for (const sourceLabels of Object.values(annotations)) {
        if (sourceLabels.numLabels > 0) noLabels = false;
      }
    }
    dispatch("labelFilters");
  });
</script>

<div
  class="absolute h-4/6 w-72 top-1/2 -translate-y-1/2 right-6 border rounded-lg shadow-xl
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500
    text-zinc-500 dark:text-zinc-300"
>
  <div class="h-12 fixed w-full flex items-center justify-evenly">
    <button
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase rounded-tl-lg
      hover:bg-zinc-100 dark:hover:bg-zinc-700
      {activeTab == 'labels'
        ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
        : 'border-zinc-300 dark:border-zinc-500'}"
      on:click={() => {
        activeTab = "labels";
      }}
    >
      Labels
    </button>
    <button
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase rounded-tr-lg
      hover:bg-zinc-100 dark:hover:bg-zinc-700
      {activeTab == 'dataset'
        ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
        : 'border-zinc-300 dark:border-zinc-500'}"
      on:click={() => {
        activeTab = "dataset";
      }}
    >
      Dataset
    </button>
  </div>
  <div class="pt-12 flex flex-col h-full">
    <div class="h-full overflow-auto {activeTab == 'labels' ? '' : 'hidden'}">
      <!-- Details -->
      <div
        class="flex flex-col p-4 border-b-2
          border-zinc-300 dark:border-zinc-500"
      >
        <span class="text-lg font-bold">Item info</span>
        <ul class="list-disc ml-6">
          {#each selectedItem.features as feature}
            {#if feature.dtype !== "image"}
              <li>
                {feature.name}: {feature.value}
              </li>
            {/if}
          {/each}
        </ul>
      </div>
      {#if noLabels}
        <p class="py-4 text-center font-bold italic">No annotations yet.</p>
      {:else}
        <div
          class="px-4 border-b-2
        border-zinc-300 dark:border-zinc-500"
        >
          <!-- Controls -->
          <div class="flex flex-col pt-2 pb-4">
            <!-- Mask opacity slider -->
            <label class="font-bold mt-2 mb-1" for="maskSlider">
              Mask opacity: {maskOpacity * 100}%
            </label>
            <input
              class="cursor-pointer"
              type="range"
              id="maskSlider"
              min="0"
              max="1"
              step="0.1"
              bind:value={maskOpacity}
              on:input={() => dispatch("labelFilters")}
            />

            <!-- BBox opacity slider -->
            <label class="font-bold mt-2 mb-1" for="bboxSlider">
              Bounding box opacity: {bboxOpacity * 100}%
            </label>
            <input
              class="cursor-pointer"
              type="range"
              id="bboxSlider"
              min="0"
              max="1"
              step="0.1"
              bind:value={bboxOpacity}
              on:input={() => dispatch("labelFilters")}
            />

            <!-- Confidence filter -->
            <label class="font-bold mt-2 mb-1" for="confidenceSlider">
              Confidence threshold: {Math.round(confidenceThreshold * 100)}%
            </label>
            <input
              class="cursor-pointer"
              type="range"
              id="confidenceSlider"
              min="0"
              max="1"
              step="0.01"
              bind:value={confidenceThreshold}
              on:input={() => dispatch("labelFilters")}
            />
          </div>
        </div>
        {#each Object.values(annotations) as source}
          {#if Object.keys(annotations).length > 1 && source.numLabels}
            <div
              class="px-3 py-5 flex items-center space-x-1 select-none border-b-2
              border-zinc-300 dark:border-zinc-500
              {source.opened ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
            >
              <button
                on:click={() => handleSourceVisibility(source, !source.visible)}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-6 w-6"
                >
                  <title>{source.visible ? "Hide" : "Show"}</title>
                  <path
                    d={source.visible ? icons.svg_hide : icons.svg_show}
                    fill="currentcolor"
                  />
                </svg>
              </button>
              <button
                class="flex grow items-center space-x-1 text-left w-full"
                on:click={() => (source.opened = !source.opened)}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-6 w-6"
                >
                  <title>{source.opened ? "Close" : "Open"}</title>
                  <path
                    d={source.opened ? icons.svg_close : icons.svg_open}
                    fill="currentcolor"
                  />
                </svg>

                <span class="relative pl-1 grow truncate w-5" title={source.id}>
                  {source.id}
                </span>
                <span
                  class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
                  title="{source.numLabels} labels"
                >
                  {source.numLabels}
                </span>
              </button>
            </div>
          {/if}
          {#each Object.values(source.views) as view}
            {#if Object.keys(source.views).length > 1 && view.numLabels}
              <div
                class="px-3 py-5 flex items-center space-x-1 select-none border-b-2
                border-zinc-300 dark:border-zinc-500
                {source.opened ? 'flex' : 'hidden'}
                {Object.keys(annotations).length > 1 ? 'pl-6' : ''}
                {view.opened ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
              >
                <button
                  on:click={() =>
                    handleViewVisibility(source, view, !view.visible)}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    height="48"
                    viewBox="0 -960 960 960"
                    width="48"
                    class="h-6 w-6"
                  >
                    <title>{view.visible ? "Hide" : "Show"}</title>
                    <path
                      d={view.visible ? icons.svg_hide : icons.svg_show}
                      fill="currentcolor"
                    />
                  </svg>
                </button>
                <button
                  class="flex items-center space-x-1 text-left w-full"
                  on:click={() => (view.opened = !view.opened)}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    height="48"
                    viewBox="0 -960 960 960"
                    width="48"
                    class="h-6 w-6"
                  >
                    <title>{view.opened ? "Close" : "Open"}</title>
                    <path
                      d={view.opened ? icons.svg_close : icons.svg_open}
                      fill="currentcolor"
                    />
                  </svg>

                  <span class="relative pl-1 grow truncate w-5" title={view.id}>
                    {view.id}
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
            {#each Object.values(view.categories) as category}
              {#if Object.keys(category.labels).length > 0}
                <div
                  class="px-3 py-5 flex items-center space-x-1 select-none border-b-2
                border-zinc-300 dark:border-zinc-500
                {source.opened && view.opened ? 'flex' : 'hidden'}
                {Object.keys(annotations).length > 1 ? 'pl-9' : 'pl-6'}
                {category.opened ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
                >
                  <button
                    on:click={() =>
                      handleCategoryVisibility(
                        source,
                        view,
                        category,
                        !category.visible
                      )}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6"
                    >
                      <title>{category.visible ? "Hide" : "Show"}</title>
                      <path
                        d={category.visible ? icons.svg_hide : icons.svg_show}
                        fill="currentcolor"
                      />
                    </svg>
                  </button>
                  <button
                    class="flex grow items-center space-x-1 text-left w-full"
                    on:click={() => (category.opened = !category.opened)}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6"
                    >
                      <title>{category.opened ? "Close" : "Open"}</title>
                      <path
                        d={category.opened ? icons.svg_close : icons.svg_open}
                        fill="currentcolor"
                      />
                    </svg>
                    <span
                      class="grow pl-1 font-bold text-zinc-800 truncate w-5"
                      title="{category.name} (id #{category.id})"
                    >
                      <button
                        class="relative px-1 rounded-lg text-sm"
                        style="background-color: {labelColors(category.id)};"
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
                <div
                  class="{source.opened && view.opened && category.opened
                    ? 'flex'
                    : 'hidden'} flex-col"
                >
                  {#each Object.values(category.labels) as label}
                    <div
                      class="p-3 pl-12 flex items-center space-x-1 border-b-2
                    {Object.keys(annotations).length > 1 ? 'pl-12' : 'pl-9'}
                    border-zinc-300 dark:border-zinc-500"
                    >
                      <button
                        on:click={() =>
                          handleLabelVisibility(
                            source,
                            view,
                            category,
                            label,
                            !label.visible
                          )}
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
                        class="relative pl-1 text-sm grow truncate w-5"
                        title={label.id}
                      >
                        {label.id}
                      </span>
                      <button on:click={() => handleDeleteLabel(label)}>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          height="48"
                          viewBox="0 -960 960 960"
                          width="48"
                          class="h-5 w-5"
                        >
                          <title>Delete</title>
                          <path d={icons.svg_delete} fill="currentcolor" />
                        </svg>
                      </button>
                    </div>
                  {/each}
                </div>
              {/if}
            {/each}
          {/each}
        {/each}
      {/if}
    </div>
    <div
      class="w-full h-full py-4 flex flex-wrap justify-center overflow-auto {activeTab ==
      'dataset'
        ? ''
        : 'hidden'}"
      on:scroll={handleDatasetScroll}
    >
      {#each selectedDataset.page.items as item, i}
        <button
          class="flex p-1 flex-col rounded
          hover:bg-zinc-100 dark:hover:bg-zinc-700"
          on:click={() => handleSelectItem(item)}
        >
          <div class="flex flex-row">
            {#each item as itemFeature}
              {#if itemFeature.dtype === "image"}
                <img
                  src={itemFeature.value}
                  alt="#{itemFeature.name}-#{i}"
                  class="w-24 h-24 p-1 object-cover rounded"
                />
              {/if}
            {/each}
          </div>
          <div class="flex">
            {#each item as itemFeature}
              {#if itemFeature.name === "id"}
                <span
                  class="text-xs text-center font-semibold w-5 truncate grow"
                  title={itemFeature.value}
                >
                  {itemFeature.value}
                </span>
              {/if}
            {/each}
          </div>
        </button>
      {/each}
    </div>
  </div>
</div>
