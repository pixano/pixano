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

  // Assets
  import svg_visible from "../../../../components/core/src/assets/icons/visible.svg";
  import svg_invisible from "../../../../components/core/src/assets/icons/invisible.svg";
  import svg_expand from "../../../../components/core/src/assets/icons/expand.svg";
  import svg_delete from "../../../../components/core/src/assets/icons/delete.svg";

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
  // Function that maps an id to a color
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
              <img
                src={view["visible"] ? svg_visible : svg_invisible}
                alt="visible"
                class="h-6 w-6 opacity-50 cursor-pointer"
                on:click={() => handleViewVisibility(view)}
              />
              <div
                class="flex grow items-center space-x-1 cursor-pointer"
                on:click={() => (view["opened"] = !view["opened"])}
              >
                <img
                  src={svg_expand}
                  alt="expand"
                  class="h-6 w-6 opacity-50
                {!view['opened'] ? '-rotate-90' : ''}"
                />
                <span class="grow ml-3 font-bold">
                  {view.view_name}
                </span>
                <span
                  class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-white font-bold"
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
                  <img
                    src={group["visible"] ? svg_visible : svg_invisible}
                    alt="visible"
                    class="h-6 w-6 opacity-50 cursor-pointer"
                    on:click={() => handleGroupVisibility(group)}
                  />
                  <div
                    class="flex grow items-center space-x-1 cursor-pointer"
                    on:click={() => (group["opened"] = !group["opened"])}
                  >
                    <img
                      src={svg_expand}
                      alt="expand"
                      class="h-6 w-6 opacity-50
                    {!group['opened'] ? '-rotate-90' : ''}"
                    />
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
                      class="h-5 w-5 flex items-center justify-center bg-rose-500 dark:bg-rose-600 rounded-full text-xs text-white font-bold"
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
                      <img
                        src={(group.visible && item.visible) || item.visible
                          ? svg_visible
                          : svg_invisible}
                        alt="visible"
                        class="h-5 w-5 opacity-50 cursor-pointer"
                        on:click={() => handleVisibility(group, item)}
                      />
                      <span
                        class="relative pl-3 grow text-sm group cursor-default"
                      >
                        {item.id}
                        <span
                          class="absolute px-2 py-1 text-zinc-700 rounded bg-zinc-50 border hidden group-hover:block"
                        >
                          label: {item.label}
                        </span>
                      </span>
                      <img
                        src={svg_delete}
                        alt="delete"
                        class="h-4 w-4 opacity-50 cursor-pointer"
                        on:click={() => deleteItem(item)}
                      />
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
