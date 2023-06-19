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
  import { createEventDispatcher } from "svelte";
  import type { AnnotationsLabels } from "../../../../components/Canvas2D/src/interfaces";

  export let annotations: Array<AnnotationsLabels>;
  export let dbImages;

  let activeTab = "labels";

  const dispatch = createEventDispatcher();

  //set classes groups opened/closed by default
  for (let group of annotations) {
    group['opened'] = false;
  }

  // Change selected tool
  function selectImage(img: string) {
    dispatch("imageSelected", img);
  }

  function deleteItem(item: any) {
    dispatch("itemDeleted", item);
  }

  function handleVisibility(group: any, item: any) {
    item.visible = !item.visible;
    if(item.visible && !group.visible) {
      group.visible = true;
    }
    dispatch("toggleVisibility", item);
  }

  function handleGroupVisibility(group: any) {
    group.visible = !group.visible;
    for (let item of group.items) {
      item.visible = group.visible;
      dispatch("toggleVisibility", item);
    }
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="w-80 shrink-0 bg-white font-[Montserrat]">
  <div class="h-12 flex items-center justify-evenly">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <span
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase cursor-pointer {activeTab ==
      'labels'
        ? 'bg-rose-100 border-rose-900 text-rose-900'
        : 'bg-zinc-100 text-zinc-500'}"
      on:click={() => {
        activeTab = "labels";
      }}
    >
      Labels
    </span>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <span
      class="w-full h-full flex justify-center items-center border-b-2 font-bold uppercase cursor-pointer {activeTab ==
      'database'
        ? 'bg-rose-100 border-rose-900 text-rose-900'
        : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200'}"
      on:click={() => {
        activeTab = "database";
      }}
    >
      Database
    </span>
  </div>
  <div class="mt-2 pb-4 flex flex-col max-h-[85vh] overflow-y-scroll">
    {#if activeTab == "labels"}
      {#each annotations as group}
        <div class="py-5 px-8 flex items-center space-x-1 select-none border-y-2 {group['opened'] ? 'bg-zinc-100' : ''}">
          <img
            src="icons/{group.visible ? 'visible' : 'invisible'}.svg"
            alt="visible"
            class="h-6 w-6 opacity-50 cursor-pointer"
            on:click={() => handleGroupVisibility(group)}
          />
          <div class="flex grow items-center space-x-1 cursor-pointer" on:click={() => (group['opened'] = !group['opened'])}>
            <img src="icons/expand.svg" alt="expand" class="h-6 w-6 {!group['opened'] ? '-rotate-90' : ''}" />
            <span class="grow ml-3 font-bold text-gray-900">
              {group.category}
            </span>
            <!-- TODO : add different colors -->
            <span
              class="h-5 w-5 flex items-center justify-center bg-rose-900 rounded-full text-xs text-white font-bold"
            >
              {group.items.length}
            </span>
          </div>
        </div>
        <div class="{group['opened'] ? 'flex' : 'hidden'} flex-col">
          {#each group.items as item, index}
            <div class="py-3 pl-12 pr-8 flex items-center space-x-1 {index === 0 ? '' : 'border-t-2'}">
              <img
                src="icons/{(group.visible && item.visible) || item.visible ? 'visible' : 'invisible'}.svg"
                alt="visible"
                class="h-5 w-5 opacity-50 cursor-pointer"
                on:click={() => handleVisibility(group, item)}
              />
              <span class="relative pl-3 grow text-sm group cursor-default">
                {item.id}
                <span class="absolute px-2 py-1 text-zinc-700 rounded bg-zinc-50 border hidden group-hover:block">
                  label: {item.label}
                </span>
              </span>
              <img
                src="icons/delete.svg"
                alt="delete"
                class="h-4 w-4 opacity-50 cursor-pointer"
                on:click={() => deleteItem(item)}
              />
            </div>
          {/each}
        </div>
      {/each}
    {:else if activeTab === "database"}
      <div class="w-full mt-4 px-10 flex flex-wrap gap-4 justify-center">
        {#each dbImages as img, i}
          <div
            class="p-2 flex flex-col rounded bg-white cursor-pointer hover:bg-zinc-200"
            on:click={() => selectImage(img)}
          >
            <img src={img} alt="image #{i}" class="w-24 h-24 object-cover rounded" />
            <span class="mt-2 text-xs font-semibold">{img}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
