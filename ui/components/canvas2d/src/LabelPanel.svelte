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
  export let annotations: ItemLabels;
  export let labelColors: Function;
  export let maskOpacity: number;
  export let bboxOpacity: number;
  export let confidenceThreshold: number;
  // Optional dataset navigation
  export let selectedDataset: Dataset = null;
  export let currentPage: number = 1;
  export let activeLearningFlag: boolean = false;

  const dispatch = createEventDispatcher();

  let activeTab = "labels"; //"dataset";
  let noLabels = true;

  function filterItems(items) {
    // Only filter if round column exists and active learning is on
    if (items[0].find((obj) => obj.name === "round") && activeLearningFlag) {
      return items.filter((subArray) => {
        const roundObj = subArray.find((obj) => obj.name === "round");
        const labelObj = subArray.find((obj) => obj.name === "label");
        return roundObj.value >= 0 && labelObj.value === null;
      });
    } else return items;
  }

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
    for (const label of Object.values(category.labels)) {
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
    for (const category of Object.values(view.categories)) {
      category.visible = view.visible;
      for (const label of Object.values(category.labels)) {
        label.visible = view.visible;
        dispatch("labelVisibility", label);
      }
    }
  }

  function handleSourceVisibility(source: SourceLabels, visibility: boolean) {
    // Toggle visibility
    source.visible = visibility;
    // Toggle children
    for (const view of Object.values(source.views)) {
      view.visible = source.visible;
      for (const category of Object.values(view.categories)) {
        category.visible = source.visible;
        for (const label of Object.values(category.labels)) {
          label.visible = source.visible;
          dispatch("labelVisibility", label);
        }
      }
    }
  }

  async function handleDatasetScroll(event: Event) {
    const datasetTab = event.currentTarget as Element;
    if (currentPage * 100 < selectedDataset.page.total) {
      const totalContentHeight =
        datasetTab.scrollHeight - datasetTab.clientHeight;
      const offset10percent = Math.ceil(totalContentHeight * 0.1);
      if (datasetTab.scrollTop > totalContentHeight - offset10percent) {
        dispatch("loadNextPage");
      }
    }
  }

  onMount(() => {
    console.log("LabelPanel.onMount");
    dispatch("labelFilters");
  });

  afterUpdate(() => {
    console.log("LabelPanel.afterUpdate");
    if (annotations) {
      annotations = annotations;
      for (const sourceLabels of Object.values(annotations)) {
        if (sourceLabels.numLabels > 0) noLabels = false;
      }
    }
    dispatch("labelFilters");

    selectedDataset.page.items = selectedDataset.page.items; // Force update
  });
</script>

<div
  class="absolute h-4/6 w-72 top-1/2 -translate-y-1/2 right-6 border rounded-lg
  shadow bg-white border-zinc-300 text-zinc-500"
>
  {#if selectedDataset}
    <div class="h-12 fixed w-full flex items-center justify-evenly">
      <button
        class="w-full h-full flex justify-center items-center border-b-2 font-semibold uppercase rounded-tl-lg
        hover:bg-zinc-100
        {activeTab == 'labels'
          ? 'bg-zinc-100 border-rose-500'
          : 'border-zinc-300 '}"
        on:click={() => {
          activeTab = "labels";
        }}
      >
        Labels
      </button>
      {#if selectedDataset}
        <button
          class="w-full h-full flex justify-center items-center border-b-2 font-semibold uppercase rounded-tr-lg
        hover:bg-zinc-100
        {activeTab == 'dataset'
            ? 'bg-zinc-100 border-rose-500 '
            : 'border-zinc-300'}"
          on:click={() => {
            activeTab = "dataset";
          }}
        >
          Dataset
        </button>
      {/if}
    </div>
  {:else}
    <div class="h-12 fixed w-full flex items-center justify-evenly">
      <button
        class="w-full h-full flex justify-center items-center border-b-2 font-semibold uppercase rounded-t-lg
          hover:bg-zinc-100
          {activeTab == 'labels'
          ? 'bg-zinc-100 border-rose-500 '
          : 'border-zinc-300 '}"
      >
        Labels
      </button>
    </div>
  {/if}
  <div class="pt-12 flex flex-col h-full">
    <div class="h-full overflow-auto {activeTab == 'labels' ? '' : 'hidden'}">
      <!-- Details -->
      <div
        class="flex flex-col p-4 border-b-2
            border-zinc-300"
      >
        <span class="font-medium"> Item information : </span>
        <ul class="list-disc ml-6">
          {#each selectedItem.features as feature}
            {#if feature.dtype !== "image"}
              <li class="break-words">
                {feature.name}: {feature.value}
              </li>
            {/if}
          {/each}
        </ul>
      </div>
      {#if noLabels}
        <p class="py-4 text-center font-medium italic">No annotations yet.</p>
      {:else}
        <div
          class="px-4 border-b-2
          border-zinc-300"
        >
          <!-- Controls -->
          <div class="flex flex-col pt-2 pb-4">
            <!-- Mask opacity slider -->
            <label class="font-medium mt-2 mb-1" for="maskSlider">
              Mask opacity: {maskOpacity * 100}%
            </label>
            <input
              class="cursor-pointer
              accent-rose-500 hover:accent-rose-600"
              type="range"
              id="maskSlider"
              min="0"
              max="1"
              step="0.1"
              bind:value={maskOpacity}
              on:input={() => dispatch("labelFilters")}
            />

            <!-- BBox opacity slider -->
            <label class="font-medium mt-2 mb-1" for="bboxSlider">
              Bounding box opacity: {bboxOpacity * 100}%
            </label>
            <input
              class="cursor-pointer
              accent-rose-500 hover:accent-rose-600"
              type="range"
              id="bboxSlider"
              min="0"
              max="1"
              step="0.1"
              bind:value={bboxOpacity}
              on:input={() => dispatch("labelFilters")}
            />

            <!-- Confidence filter -->
            <label class="font-medium mt-2 mb-1" for="confidenceSlider">
              Confidence threshold: {Math.round(confidenceThreshold * 100)}%
            </label>
            <input
              class="cursor-pointer
              accent-rose-500 hover:accent-rose-600"
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
                border-zinc-300
                {source.opened ? 'bg-zinc-100' : ''}"
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
                  class="h-5 w-5 flex items-center justify-center bg-rose-500 rounded-full text-xs text-zinc-50 font-medium"
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
                  border-zinc-300
                  {source.opened ? 'flex' : 'hidden'}
                  {Object.keys(annotations).length > 1 ? 'pl-6' : ''}
                  {view.opened ? 'bg-zinc-100 ' : ''}"
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
                    class="h-5 w-5 flex items-center justify-center bg-rose-500 rounded-full text-xs text-zinc-50 font-medium"
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
                  border-zinc-300
                  {source.opened && view.opened ? 'flex' : 'hidden'}
                  {Object.keys(annotations).length > 1 ? 'pl-9' : 'pl-6'}
                  {category.opened ? 'bg-zinc-100' : ''}"
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
                      class="grow pl-1 font-medium text-zinc-800 truncate w-5"
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
                      class="h-5 w-5 flex items-center justify-center bg-rose-500 rounded-full text-xs text-zinc-50 font-medium"
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
                      border-zinc-300"
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
    {#if selectedDataset}
      <div
        class="w-full h-full overflow-y-scroll {activeTab == 'dataset'
          ? ''
          : 'hidden'}"
      >
        <!-- Details -->
        <div class="flex flex-col p-4 border-b-2 border-zinc-300">
          <span class="font-medium"> Active learning : </span>
          <label class="pt-1 flex items-center select-none cursor-pointer">
            <input
              type="checkbox"
              class="cursor-pointer mx-2"
              bind:checked={activeLearningFlag}
            />
            Show remaining items only
          </label>
        </div>

        <div
          class="p-4 flex flex-wrap justify-center"
          on:scroll={handleDatasetScroll}
        >
          {#each filterItems(selectedDataset.page.items) as item, i}
            <button
              class="flex p-1 flex-col rounded h-min hover:bg-zinc-100"
              on:click={() => handleSelectItem(item)}
            >
              <div
                class={item.filter((f) => f.dtype === "image").length > 1
                  ? "grid grid-cols-2"
                  : ""}
              >
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
              <div class="flex mx-auto">
                <span
                  class="text-xs justify-center truncate grow
                  {item.filter((f) => f.dtype === 'image').length > 1
                    ? 'w-48'
                    : 'w-24'}"
                  title={item.find((f) => f.name === "id").value}
                >
                  {item.find((f) => f.name === "id").value.length > 12
                    ? item.find((f) => f.name === "id").value.substring(0, 6) +
                      "..." +
                      item.find((f) => f.name === "id").value.slice(-6)
                    : item.find((f) => f.name === "id").value}
                </span>
              </div>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
