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

  import type {
    AnnotationsLabels,
    DatabaseFeats,
  } from "../../../../components/canvas2d/src/interfaces";

  // Exports
  export let annotations: Array<AnnotationsLabels>;
  export let dataset: DatabaseFeats = null;
  export let lastLoadedPage: number;
  export let categoryColor = null;

  // Icons
  const svg_visible =
    "M480.118-330Q551-330 600.5-379.618q49.5-49.617 49.5-120.5Q650-571 600.382-620.5q-49.617-49.5-120.5-49.5Q409-670 359.5-620.382q-49.5 49.617-49.5 120.5Q310-429 359.618-379.5q49.617 49.5 120.5 49.5Zm-.353-58Q433-388 400.5-420.735q-32.5-32.736-32.5-79.5Q368-547 400.735-579.5q32.736-32.5 79.5-32.5Q527-612 559.5-579.265q32.5 32.736 32.5 79.5Q592-453 559.265-420.5q-32.736 32.5-79.5 32.5ZM480-200q-146 0-264-83T40-500q58-134 176-217t264-83q146 0 264 83t176 217q-58 134-176 217t-264 83Zm0-300Zm-.169 240Q601-260 702.5-325.5 804-391 857-500q-53-109-154.331-174.5-101.332-65.5-222.5-65.5Q359-740 257.5-674.5 156-609 102-500q54 109 155.331 174.5 101.332 65.5 222.5 65.5Z";
  const svg_invisible =
    "m629-419-44-44q26-71-27-118t-115-24l-44-44q17-11 38-16t43-5q71 0 120.5 49.5T650-500q0 22-5.5 43.5T629-419Zm129 129-40-40q49-36 85.5-80.5T857-500q-50-111-150-175.5T490-740q-42 0-86 8t-69 19l-46-47q35-16 89.5-28T485-800q143 0 261.5 81.5T920-500q-26 64-67 117t-95 93Zm58 226L648-229q-35 14-79 21.5t-89 7.5q-146 0-265-81.5T40-500q20-52 55.5-101.5T182-696L56-822l42-43 757 757-39 44ZM223-654q-37 27-71.5 71T102-500q51 111 153.5 175.5T488-260q33 0 65-4t48-12l-64-64q-11 5-27 7.5t-30 2.5q-70 0-120-49t-50-121q0-15 2.5-30t7.5-27l-97-97Zm305 142Zm-116 58Z";
  const svg_closed = "m375-240-43-43 198-198-198-198 43-43 241 241-241 241Z";
  const svg_opened = "M480-345 240-585l43-43 197 198 197-197 43 43-240 239Z";
  const svg_delete =
    "M261-120q-24.75 0-42.375-17.625T201-180v-570h-41v-60h188v-30h264v30h188v60h-41v570q0 24-18 42t-42 18H261Zm438-630H261v570h438v-570ZM367-266h60v-399h-60v399Zm166 0h60v-399h-60v399ZM261-750v570-570Z";

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
    text-zinc-900 dark:text-zinc-300
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500"
>
  <div class="h-12 fixed w-full flex items-center justify-evenly">
    <span
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase cursor-pointer rounded-tl-lg
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
    </span>
    <span
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase cursor-pointer rounded-tr-lg
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
    </span>
  </div>
  <div class="pt-12 flex flex-col h-full">
    <div class="h-full overflow-auto {activeTab == 'labels' ? '' : 'hidden'}">
      {#if annotations.length != 0}
        {#each view_list as view}
          {#if view_list.length > 1}
            <div
              class="py-5 px-8 flex items-center space-x-1 select-none border-b-2
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
                    d={view["visible"] ? svg_visible : svg_invisible}
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
                    d={view["opened"] ? svg_opened : svg_closed}
                    fill="currentcolor"
                  />
                </svg>

                <span class="grow ml-3 font-bold">
                  {view.view_name}
                </span>
                <span
                  class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-zinc-50 font-bold"
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
                  class="py-5 px-8 flex items-center space-x-1 select-none
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
                        d={group["visible"] ? svg_visible : svg_invisible}
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
                        d={group["opened"] ? svg_opened : svg_closed}
                        fill="currentcolor"
                      />
                    </svg>
                    <span class="grow ml-3 font-bold text-gray-900">
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
                    >
                      {group.items.length}
                    </span>
                  </div>
                </div>
                <div class="{group['opened'] ? 'flex' : 'hidden'} flex-col">
                  {#each group.items as item, index}
                    <div
                      class="py-3 pl-12 pr-8 flex items-center space-x-1
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
                              ? svg_visible
                              : svg_invisible}
                            fill="currentcolor"
                          />
                        </svg>
                      </button>
                      <span class="relative pl-3 text-sm grow group">
                        {item.id}
                        <span
                          class="absolute z-10 px-2 py-1 rounded border hidden group-hover:block
                          text-zinc-700 bg-zinc-50"
                        >
                          id: {item.id} <br />
                          label: {item.label}
                        </span>
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
