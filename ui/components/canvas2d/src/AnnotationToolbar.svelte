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
  import type { Tool } from "./tools";

  // Exports
  export let tools_lists: Array<Array<Tool>> = [];
  export let selectedTool: Tool = null;

  function selectTool(tool: Tool) {
    // Prevent re-selecting the active tool
    if (tool !== selectedTool) selectedTool = tool;
  }
</script>

<div class="absolute top-1/2 -translate-y-1/2 left-6">
  {#each tools_lists as tools}
    <div
      class="m-4 flex flex-col border rounded-lg
      shadow bg-slate-50 border-slate-300"
    >
      <div class="flex flex-col items-center">
        {#each tools as tool}
          {#if tool["modes"]}
            <div class="relative group">
              <button class="p-4" on:click={() => selectTool(tool["modes"][0])}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-10 w-10 p-1 border-2 rounded
                  bg-slate-50 hover:bg-slate-300
                  {tool['modes'].includes(selectedTool)
                    ? 'border-main'
                    : 'border-transparent'}"
                >
                  <title>{tool.name}</title>
                  <path d={tool.icon} fill="currentcolor" />
                </svg>
              </button>

              <div
                class="absolute inset-y-0 left-16 border rounded-lg z-10 hidden group-hover:flex
                shadow bg-slate-50 border-slate-300"
              >
                {#each tool["modes"] as mode}
                  <button class="w-full p-4" on:click={() => selectTool(mode)}>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      height="48"
                      viewBox="0 -960 960 960"
                      width="48"
                      class="h-10 w-10 p-1 border-2 rounded
                      bg-slate-50 hover:bg-slate-300
                      {mode === selectedTool
                        ? 'border-main'
                        : 'border-transparent'}"
                    >
                      <title>{mode.name}</title>
                      <path d={mode.icon} fill="currentcolor" />
                    </svg>
                  </button>
                {/each}
              </div>
            </div>
          {:else}
            <button class="p-4" on:click={() => selectTool(tool)}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                height="48"
                viewBox="0 -960 960 960"
                width="48"
                class="h-10 w-10 p-1 border-2 rounded
                bg-slate-50 hover:bg-slate-300
                {selectedTool === tool ? 'border-main' : 'border-transparent'}"
              >
                <title>{tool.name}</title>
                <path d={tool.icon} fill="currentcolor" />
              </svg>
            </button>
          {/if}
        {/each}
      </div>
    </div>
  {/each}
</div>
