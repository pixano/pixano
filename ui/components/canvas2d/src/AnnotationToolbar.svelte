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
  class="absolute top-1/2 -translate-y-1/2 left-6 py-2 px-4 flex flex-col border rounded-lg shadow-xl
    bg-white dark:bg-zinc-800
    border-zinc-300 dark:border-zinc-500"
>
  <div class="flex flex-col items-center">
    {#each tools as tool}
      {#if tool["modes"]}
        <div class="relative group">
          <button class="py-3" on:click={() => selectTool(tool["modes"][0])}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-10 w-10 p-1 border-2 rounded
              bg-white dark:bg-zinc-800
              hover:bg-zinc-200 dark:hover:bg-zinc-600
              {tool['modes'].includes(selectedTool)
                ? 'border-rose-500 dark:border-rose-600'
                : 'border-transparent'}
                "
            >
              <title>{tool.name}</title>
              <path d={tool.icon} fill="currentcolor" />
            </svg>
          </button>

          <div
            class="absolute inset-y-0 border rounded left-full z-10 hidden group-hover:flex
            bg-white dark:bg-zinc-800
            border-zinc-300 dark:border-zinc-500"
          >
            {#each tool["modes"] as mode}
              <button class="w-full p-2" on:click={() => selectTool(mode)}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-10 w-10 p-1 border-2 rounded
                  bg-white dark:bg-zinc-800
                  hover:bg-zinc-200 dark:hover:bg-zinc-600
                  {mode === selectedTool
                    ? 'border-rose-500 dark:border-rose-600'
                    : 'border-transparent'}
                    "
                >
                  <title>{mode.name}</title>
                  <path d={mode.icon} fill="currentcolor" />
                </svg>
              </button>
            {/each}
          </div>
        </div>
      {:else}
        <button class="py-3" on:click={() => selectTool(tool)}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-10 w-10 p-1 border-2 rounded
            bg-white dark:bg-zinc-800
            hover:bg-zinc-200 dark:hover:bg-zinc-600
            {selectedTool === tool
              ? 'border-rose-500 dark:border-rose-600'
              : 'border-transparent'}
              "
          >
            <title>{tool.name}</title>
            <path d={tool.icon} fill="currentcolor" />
          </svg>
        </button>
      {/if}
    {/each}
  </div>
</div>
