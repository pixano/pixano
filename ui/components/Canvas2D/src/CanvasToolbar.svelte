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
<div class="w-20 shrink-0">
  <div class="mt-4 flex flex-col items-center">
    {#each tools as tool}
      {#if tool["modes"]}
        <div
          class="relative group w-full border-r-4 {tool['modes'].includes(
            selectedTool
          )
            ? 'bg-rose-100 border-rose-900'
            : 'hover:bg-rose-50 border-transparent'}"
        >
          <div
            class="w-full py-3 cursor-pointer"
            on:click={() => selectTool(tool["modes"][0])}
          >
            <img class="w-6 h-6 mx-auto" src={tool.icon} alt={tool.name} />
          </div>

          <div
            class="absolute top-0 left-full w-28 bg-white z-10 hidden group-hover:flex"
          >
            {#each tool["modes"] as mode}
              <div
                class="w-full cursor-pointer border-b-2 {mode === selectedTool
                  ? 'bg-rose-100 border-rose-900'
                  : 'hover:bg-rose-50 border-transparent'}"
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
          class="w-full border-r-4 cursor-pointer {selectedTool === tool
            ? 'bg-rose-100 border-rose-900'
            : 'hover:bg-rose-50 border-transparent'}"
          on:click={() => selectTool(tool)}
        >
          <img class="w-6 h-6 my-3 mx-auto" src={tool.icon} alt={tool.name} />
        </div>
      {/if}
    {/each}
    <div class="mt-3 w-10 border" />
  </div>
</div>
