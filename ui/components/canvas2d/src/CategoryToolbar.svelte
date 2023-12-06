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

  import { icons } from "@pixano/core";

  import { ToolType } from "./tools";

  import type { DatasetCategory } from "@pixano/core";
  import type { PointSelectionTool, Tool } from "./tools";

  // Exports
  export let currentAnnCatName: string;
  export let classes: Array<DatasetCategory>;
  export let selectedTool: Tool;
  export let pointSelectionTool: PointSelectionTool;
  export let colorScale: (id: string) => string;
  export let placeholder: string = "Category name";

  const dispatch = createEventDispatcher();

  function handleAddCurrentAnn() {
    dispatch("addCurrentAnn");
  }

  function handleFilterCategories() {
    // Input filter
    const input = document.getElementById("categoryInput") as HTMLInputElement;
    const filter = input.value.toUpperCase();
    // Category list
    const list = document.getElementById("category_list");
    const a = list.getElementsByTagName("button");
    for (let i = 0; i < a.length; i++) {
      const txtValue = a[i].textContent || a[i].innerText;
      if (txtValue.toUpperCase().indexOf(filter) > -1) {
        a[i].style.display = "";
      } else {
        a[i].style.display = "none";
      }
    }
  }

  function handleKeyPress(event: KeyboardEvent) {
    if (event.key === "Enter") {
      dispatch("addCurrentAnn");
    }
  }

  function focusInput() {
    const input = document.getElementById("categoryInput");
    input.focus();
  }

  afterUpdate(() => {
    handleFilterCategories();
  });
</script>

<div
  class="absolute top-24 left-1/2 -translate-x-1/2 p-4 flex items-center space-x-4 border rounded-lg z-10
  shadow bg-slate-50 border-slate-300"
>
  <div class="group">
    <input
      type="text"
      {placeholder}
      id="categoryInput"
      class="h-10 py-1 px-2 w-80 border-2 rounded focus:outline-none
      bg-slate-100 border-slate-300 focus:border-main"
      on:keyup={handleFilterCategories}
      on:keydown={handleKeyPress}
      bind:value={currentAnnCatName}
    />

    <div
      id="category_list"
      class="absolute left-4 w-80 top-14 hidden rounded-lg py-1 group-focus-within:flex hover:flex flex-col
      shadow bg-slate-50"
      style="overflow-y:scroll; max-height: 500px;"
    >
      {#each classes as cls}
        <button
          class="relative my-1 mx-2 px-2 py-1 rounded-lg text-sm flex text-slate-800 font-medium hover:brightness-110"
          style="background-color: {colorScale(cls.id.toString())}; text-align:left"
          title="{cls.name} (id #{cls.id})"
          on:click={() => {
            focusInput();
            currentAnnCatName = cls.name;
          }}
        >
          {cls.name}
        </button>
      {/each}
    </div>
  </div>

  {#if selectedTool.type === ToolType.PointSelection}
    <button
      on:click={() => {
        selectedTool = pointSelectionTool.modes.plus;
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="h-10 w-10 p-1 border-2 rounded
        bg-slate-50 hover:bg-slate-300
        {selectedTool === pointSelectionTool.modes['plus'] ? 'border-main' : 'border-transparent'}"
      >
        <title>{pointSelectionTool.modes.plus.name}</title>
        <path d={pointSelectionTool.modes.plus.icon} fill="currentcolor" />
      </svg>
    </button>
    <button
      on:click={() => {
        selectedTool = pointSelectionTool.modes.minus;
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="h-10 w-10 p-1 border-2 rounded
        bg-slate-50 hover:bg-slate-300
        {selectedTool === pointSelectionTool.modes['minus']
          ? 'border-main '
          : 'border-transparent'}"
      >
        <title>{pointSelectionTool.modes.minus.name}</title>
        <path d={pointSelectionTool.modes.minus.icon} fill="currentcolor" />
      </svg>
    </button>
  {/if}
  <button on:click={handleAddCurrentAnn}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="48"
      viewBox="0 -960 960 960"
      width="48"
      class="h-10 w-10 p-1 rounded border border-transparent text-slate-50
      bg-main hover:bg-secondary"
    >
      <title>Validate</title>
      <path d={icons.svg_validate} fill="currentcolor" />
    </svg>
  </button>
</div>
