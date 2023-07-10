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
  import { type Tool } from "./tools";

  // Exports
  export let tools: Array<Tool> = [];
  export let selectedTool: Tool = null;

  const dispatch = createEventDispatcher();

  // Change selected tool
  function selectTool(tool: Tool) {
    if (tool === selectedTool) return; // Prevent re-selecting the active tool
    selectedTool = tool;
    dispatch("toolSelected", selectTool);
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div
  class="absolute w-24 top-1/2 -translate-y-1/2 left-6 py-2 px-4 flex flex-col border rounded-lg shadow-xl
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500"
>
  <div class="flex flex-col items-center">
    {#each tools as tool}
      {#if tool["modes"]}
        <div
          class="relative group w-full border-b-2
          hover:bg-zinc-100 dark:hover:bg-zinc-700
          {tool['modes'].includes(selectedTool)
            ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
            : 'border-transparent'}"
        >
          <div
            class="w-full py-3 cursor-pointer"
            on:click={() => selectTool(tool["modes"][0])}
          >
            <img class="w-6 h-6 mx-auto" src={tool.icon} alt={tool.name} />
          </div>

          <div
            class="absolute top-0 left-full w-28 z-10 hidden group-hover:flex
            bg-white dark:bg-zinc-800"
          >
            {#each tool["modes"] as mode}
              <div
                class="w-full cursor-pointer border-b-2
                hover:bg-zinc-100 dark:hover:bg-zinc-700
                {mode === selectedTool
                  ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
                  : 'border-transparent'}"
                on:click={() => selectTool(mode)}
              >
                <img
                  class="w-6 h-6 my-3 mx-auto"
                  src={mode.icon}
                  alt={mode.name}
                />
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div
          class="w-full border-b-2 cursor-pointer
          hover:bg-zinc-100 dark:hover:bg-zinc-700
          {selectedTool === tool
            ? 'bg-zinc-100 dark:bg-zinc-700 border-rose-500 dark:border-rose-600'
            : 'border-transparent'}"
          on:click={() => selectTool(tool)}
        >
          <img class="w-6 h-6 my-3 mx-auto" src={tool.icon} alt={tool.name} />
        </div>
      {/if}
    {/each}
  </div>
</div>
