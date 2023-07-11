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
  import { afterUpdate, createEventDispatcher } from "svelte";

  import {
    svg_hide,
    svg_show,
    svg_open,
    svg_close,
    svg_delete,
  } from "../../../../components/core/src/icons";
  import type {
    AnnotationsLabels,
    DatabaseFeats,
  } from "../../../../components/canvas2d/src/interfaces";

  // Exports
  export let annotations: Array<AnnotationsLabels>;
  export let dataset: DatabaseFeats = null;
  export let lastLoadedPage: number;
  export let categoryColor = null;

  let d_data = [];

  let view_list = []; //view that contains annotations for anns display (not real views list)
  let activeTab = "labels"; //"database";
  const dispatch = createEventDispatcher();

  //set classes groups opened/closed by default
  for (let group of annotations) {
    group["opened"] = false;
  }

  // Change selected image
  function selectImage(img) {
    dispatch("imageSelected", img);
  }

  function deleteItem(item: any) {
    dispatch("itemDeleted", item);
  }

  function handleVisibility(group: any, item: any) {
    item.visible = !item.visible;
    if (item.visible && !group.visible) {
      group.visible = true;
    }
    //add viewId info
    let detail = item;
    detail.viewId = group.viewId;
    dispatch("toggleVisibility", detail);
  }

  function handleGroupVisibility(group: any) {
    group.visible = !group.visible;
    for (let item of group.items) {
      item.visible = group.visible;
      //add viewId info
      let detail = item;
      detail.viewId = group.viewId;
      dispatch("toggleVisibility", detail);
    }
  }

  function handleViewVisibility(view: any) {
    view.visible = !view.visible;
    for (let ann of annotations) {
      if (ann.viewId === view.view_name) {
        handleGroupVisibility(ann);
      }
    }
    //hack to refresh icon
    view_list = view_list;
  }

  async function handleDatabaseScroll(event) {
    if (lastLoadedPage * 100 < dataset.total) {
      const totalContentHeight =
        event.target.scrollHeight - event.target.clientHeight;
      const offset10percent = Math.ceil(totalContentHeight * 0.1);
      if (event.target.scrollTop > totalContentHeight - offset10percent) {
        dispatch("loadNextPage");
      }
    }
  }

  afterUpdate(() => {
    /*
    if (view_list) {
      view_list = view_list;
    }
    */
    if (annotations) {
      //build views list
      let viewIds = new Set();
      view_list = [];
      for (let ann of annotations) {
        viewIds.add(ann.viewId);
      }
      for (let viewId of viewIds) {
        let num_objs = 0;
        for (let ann of annotations) {
          if (ann.viewId === viewId) {
            num_objs += ann.items.length;
          }
        }
        view_list.push({
          view_name: viewId,
          opened: true,
          visible: true,
          num_objs: num_objs,
        });
      }
    }

    if (dataset && dataset.items) {
      //build weel-formed dataset from dataset input
      d_data = [];
      for (let feats of dataset.items) {
        let data = { views: [] };
        for (let feat of feats) {
          if (feat.dtype === "image") {
            data.views.push({ viewId: feat.name, img: feat.value });
          } else {
            data[feat.name] = feat.value;
          }
        }
        d_data.push(data);
      }
    }
  });
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
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
      {activeTab == 'database'
        ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
        : 'border-zinc-300 dark:border-zinc-500'}"
      on:click={() => {
        activeTab = "database";
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
              <div
                class="flex grow items-center space-x-1 cursor-pointer"
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
                  title="{view.num_objs} items"
                >
                  {view.num_objs}
                </span>
              </div>
            </div>
          {/if}
          {#each annotations as group}
            {#if group.viewId === view.view_name}
              <div
                class="{view['opened']
                  ? 'flex'
                  : 'hidden'} flex-col border-b-2 last:border-transparent
                  border-zinc-300 dark:border-zinc-500"
              >
                <div
                  class="p-5 flex items-center space-x-1 select-none
                  {group['opened'] ? 'bg-zinc-100 dark:bg-zinc-700' : ''}"
                >
                  <button on:click={() => handleGroupVisibility(group)}>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6 text-zinc-500 dark:text-zinc-300"
                    >
                      <title>{group["visible"] ? "Hide" : "Show"}</title>
                      <path
                        d={group["visible"] ? svg_hide : svg_show}
                        fill="currentcolor"
                      />
                    </svg>
                  </button>
                  <div
                    class="flex grow items-center space-x-1 cursor-pointer"
                    on:click={() => (group["opened"] = !group["opened"])}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-6 w-6 text-zinc-500 dark:text-zinc-300"
                    >
                      <title>{group["opened"] ? "Close" : "Open"}</title>
                      <path
                        d={group["opened"] ? svg_close : svg_open}
                        fill="currentcolor"
                      />
                    </svg>
                    <span class="grow ml-3 font-bold text-zinc-800">
                      <button
                        class="relative px-1 rounded-lg text-sm"
                        style="background-color: {categoryColor(
                          group.category_id
                        )};"
                      >
                        {group.category_name}
                      </button>
                    </span>
                    <span
                      class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
                      title="{group.items.length} items"
                    >
                      {group.items.length}
                    </span>
                  </div>
                </div>
                <div class="{group['opened'] ? 'flex' : 'hidden'} flex-col">
                  {#each group.items as item, index}
                    <div
                      class="py-3 px-8 flex items-center space-x-1
                      {index === 0 ? '' : 'border-t-2'}
                      border-zinc-300 dark:border-zinc-500"
                    >
                      <button on:click={() => handleVisibility(group, item)}>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          height="48"
                          viewBox="0 -960 960 960"
                          width="48"
                          class="h-5 w-5 text-zinc-500 dark:text-zinc-300"
                        >
                          <title>
                            {(group.visible && item.visible) || item.visible
                              ? "Hide"
                              : "Show"}
                          </title>
                          <path
                            d={(group.visible && item.visible) || item.visible
                              ? svg_hide
                              : svg_show}
                            fill="currentcolor"
                          />
                        </svg>
                      </button>
                      <span
                        class="relative pl-3 text-sm grow truncate"
                        title="{item.id} ({item.label})"
                      >
                        {item.id}
                      </span>
                      <button on:click={() => deleteItem(item)}>
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
      'database'
        ? ''
        : 'hidden'}"
      on:scroll={handleDatabaseScroll}
    >
      {#each d_data as data, i}
        <div
          class="p-2 flex flex-col rounded cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-700"
          on:click={() => selectImage(data)}
        >
          <div class="flex flex-row">
            {#each data.views as view}
              <img
                src={view.img}
                alt="#{view}-#{i}"
                class="w-24 h-24 object-cover rounded"
              />
            {/each}
          </div>
          <span class="w-24 mt-2 text-xs font-semibold">{data.id}</span>
        </div>
      {/each}
    </div>
  </div>
</div>
