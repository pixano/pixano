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
  import { afterUpdate, createEventDispatcher } from "svelte";

  import {
    svg_close,
    svg_delete,
    svg_hide,
    svg_open,
    svg_show,
  } from "@pixano/core/src/icons";

  import type {
    AnnotationLabel,
    AnnotationCategory,
    DatasetItems,
    DatasetItemFeature,
  } from "@pixano/canvas2d/src/interfaces";

  // Exports
  export let annotations: Array<AnnotationCategory>;
  export let datasetItems: DatasetItems = null;
  export let currentPage: number;
  export let categoryColor = null;

  let view_list = []; //view that contains annotations for anns display (not real views list)
  let activeTab = "labels"; //"dataset";
  const dispatch = createEventDispatcher();

  // Set categories as closed by default
  for (let category of annotations) {
    category["opened"] = false;
  }

  // Change selected image
  function handleSelectItem(item: DatasetItemFeature[]) {
    dispatch("selectItem", item);
  }

  function handleDeleteLabel(label: AnnotationLabel) {
    dispatch("deleteLabel", label);
  }

  function handleLabelVisibility(
    view: any,
    category: AnnotationCategory,
    label: AnnotationLabel
  ) {
    label.visible = !label.visible;
    if (label.visible && !view.visible) {
      view.visible = true;
    }
    if (label.visible && !category.visible) {
      category.visible = true;
    }
    dispatch("labelVisibility", label);
  }

  function handleCategoryVisibility(view: any, category: AnnotationCategory) {
    category.visible = !category.visible;
    if (category.visible && !view.visible) {
      view.visible = true;
    }
    for (let label of category.labels) {
      label.visible = category.visible;
      dispatch("labelVisibility", label);
    }
  }

  function handleViewVisibility(view: any) {
    view.visible = !view.visible;
    for (let category of annotations) {
      if (category.viewId === view.view_name) {
        category.visible = view.visible;
        for (let label of category.labels) {
          label.visible = category.visible;
          dispatch("labelVisibility", label);
        }
      }
    }
  }

  async function handleDatasetScroll(event) {
    if (currentPage * 100 < datasetItems.total) {
      const totalContentHeight =
        event.target.scrollHeight - event.target.clientHeight;
      const offset10percent = Math.ceil(totalContentHeight * 0.1);
      if (event.target.scrollTop > totalContentHeight - offset10percent) {
        dispatch("loadNextPage");
      }
    }
  }

  afterUpdate(() => {
    if (annotations) {
      //build views list
      let viewIds = new Set();
      for (let ann of annotations) {
        viewIds.add(ann.viewId);
      }
      for (let viewId of viewIds) {
        let num_objs = 0;
        for (let ann of annotations) {
          if (ann.viewId === viewId) {
            num_objs += ann.labels.length;
          }
        }
        let vl = view_list.find((v) => v.view_name == viewId);
        if (vl) {
          vl.num_objs = num_objs;
          //hack for svelte refresh
          view_list = view_list;
        } else {
          view_list.push({
            view_name: viewId,
            opened: true,
            visible: true,
            num_objs: num_objs,
          });
        }
      }
    }
  });
</script>

<div
  class="absolute h-4/6 w-72 top-1/2 -translate-y-1/2 right-6 border rounded-lg shadow-xl
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500"
>
  <div class="h-12 fixed w-full flex items-center justify-evenly">
    <button
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase rounded-tl-lg
      text-zinc-500 dark:text-zinc-300
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
      text-zinc-500 dark:text-zinc-300
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
      {#if annotations.length != 0}
        {#each view_list as view}
          {#if view_list.length > 1}
            <div
              class="p-5 flex items-center space-x-1 select-none border-b-2
            border-zinc-300 dark:border-zinc-500
            {view['opened'] ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
            >
              <button on:click={() => handleViewVisibility(view)}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-6 w-6 text-zinc-500 dark:text-zinc-300"
                >
                  <title>{view["visible"] ? "Hide" : "Show"}</title>
                  <path
                    d={view["visible"] ? svg_hide : svg_show}
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
                  class="h-6 w-6 text-zinc-500 dark:text-zinc-300"
                >
                  <title>{view["opened"] ? "Close" : "Open"}</title>
                  <path
                    d={view["opened"] ? svg_close : svg_open}
                    fill="currentcolor"
                  />
                </svg>

                <span
                  class="grow ml-3 font-bold text-zinc-500 dark:text-zinc-300"
                >
                  {view.view_name}
                </span>
                <span
                  class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
                  title="{view.num_objs} labels"
                >
                  {view.num_objs}
                </span>
              </button>
            </div>
          {/if}
          {#each annotations as category}
            {#if category.viewId === view.view_name}
              <div
                class="{view['opened']
                  ? 'flex'
                  : 'hidden'} flex-col border-b-2 last:border-transparent
                  border-zinc-300 dark:border-zinc-500"
              >
                <div
                  class="p-5 flex items-center space-x-1 select-none
                  {category['opened'] ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
                >
                  <button
                    on:click={() => handleCategoryVisibility(view, category)}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6 text-zinc-500 dark:text-zinc-300"
                    >
                      <title>{category["visible"] ? "Hide" : "Show"}</title>
                      <path
                        d={category["visible"] ? svg_hide : svg_show}
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
                      class="h-6 w-6 text-zinc-500 dark:text-zinc-300"
                    >
                      <title>{category["opened"] ? "Close" : "Open"}</title>
                      <path
                        d={category["opened"] ? svg_close : svg_open}
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
                      title="{category.labels.length} labels"
                    >
                      {category.labels.length}
                    </span>
                  </button>
                </div>
                <div class="{category['opened'] ? 'flex' : 'hidden'} flex-col">
                  {#each category.labels as label, index}
                    <div
                      class="py-3 px-8 flex items-center space-x-1
                      {index === 0 ? '' : 'border-t-2'}
                      border-zinc-300 dark:border-zinc-500"
                    >
                      <button
                        on:click={() =>
                          handleLabelVisibility(view, category, label)}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          height="48"
                          viewBox="0 -960 960 960"
                          width="48"
                          class="h-5 w-5 text-zinc-500 dark:text-zinc-300"
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
                              ? svg_hide
                              : svg_show}
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
                      <button on:click={() => handleDeleteLabel(label)}>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          height="48"
                          viewBox="0 -960 960 960"
                          width="48"
                          class="h-5 w-5 text-zinc-500 dark:text-zinc-300"
                        >
                          <title>Delete</title>
                          <path d={svg_delete} fill="currentcolor" />
                        </svg>
                      </button>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          {/each}
        {/each}
      {:else}
        <p
          class="py-4 text-center font-bold italic
          text-zinc-500 dark:text-zinc-300"
        >
          No annotations yet.
        </p>
      {/if}
    </div>
    <div
      class="w-full h-full py-4 flex flex-wrap justify-center overflow-auto {activeTab ==
      'dataset'
        ? ''
        : 'hidden'}"
      on:scroll={handleDatasetScroll}
    >
      {#each datasetItems.items as item, i}
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
          {#each item as itemFeature}
            {#if itemFeature.name === "id"}
              <span class="text-xs text-center font-semibold"
                >{itemFeature.value}</span
              >
            {/if}
          {/each}
        </button>
      {/each}
    </div>
  </div>
</div>
